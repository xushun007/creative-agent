"""Codex核心引擎"""

import asyncio
from typing import Optional, AsyncIterator
from pathlib import Path

from .config import Config
from .session import Session
from .protocol import Op, Event, Submission
from utils.logger import logger


class CodexEngine:
    """Codex核心引擎"""
    
    def __init__(self, config: Config, memory_manager=None):
        self.config = config
        self.session: Optional[Session] = None
        self._running = False
        self._memory_manager = memory_manager  # 保存恢复的 memory_manager
    
    async def start(self) -> Session:
        """启动Codex引擎"""
        if self.session:
            await self.session.stop()
        
        # 创建新会话（或使用恢复的会话）
        self.session = Session(self.config, memory_manager=self._memory_manager)
        await self.session.start()
        
        # 启动会话处理循环
        self._running = True
        asyncio.create_task(self._process_loop())
        
        return self.session
    
    async def stop(self):
        """停止Codex引擎"""
        self._running = False
        
        if self.session:
            await self.session.stop()
            self.session = None
    
    async def submit_user_input(self, text: str, cwd: Optional[Path] = None) -> str:
        """提交用户输入"""
        if not self.session:
            raise RuntimeError("会话未启动")
        
        op = Op.user_input(text, cwd)
        submission_id = await self.session.submit_operation(op)
        return submission_id
    
    async def interrupt_current_task(self) -> str:
        """中断当前任务"""
        if not self.session:
            raise RuntimeError("会话未启动")
        
        op = Op.interrupt()
        submission_id = await self.session.submit_operation(op)
        return submission_id
    
    async def approve_execution(self, submission_id: str, approved: bool) -> str:
        """批准或拒绝执行"""
        if not self.session:
            raise RuntimeError("会话未启动")
        
        decision = "approved" if approved else "denied"
        op = Op.exec_approval(submission_id, decision)
        approval_id = await self.session.submit_operation(op)
        return approval_id
    
    async def get_events(self) -> AsyncIterator[Event]:
        """获取事件流"""
        if not self.session:
            raise RuntimeError("会话未启动")
        
        while self._running:
            event = await self.session.get_next_event()
            if event:
                yield event
            elif not self._running:
                break
            else:
                await asyncio.sleep(0.1)
    
    async def _process_loop(self):
        """会话处理循环"""
        if not self.session:
            return
        
        try:
            await self.session.process_submissions()
        except Exception as e:
            logger.error(f"会话处理循环出错: {e}")
        finally:
            self._running = False
    
    @property
    def is_running(self) -> bool:
        """检查引擎是否正在运行"""
        return self._running and self.session is not None
    
    @property
    def token_usage(self):
        """获取token使用情况"""
        if self.session:
            return self.session.total_token_usage
        return None
