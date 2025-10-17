"""Codex会话管理"""

import asyncio
import json
from typing import Optional, Dict, Any
import uuid

from .protocol import (
    Submission, Event, EventMsg, Op, TokenUsage
)
from .config import Config
from .model_client import Message, ModelClient
from .event_handler import EventHandler
from .compaction.manager import CompactionManager
from .compaction.strategies.opencode import OpenCodeStrategy
from .compaction.base import CompactionContext
from utils.logger import logger


class Session:
    """Codex会话"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session_id = str(uuid.uuid4())
        
        # 集成工具注册系统
        from tools.registry import get_global_registry
        self.tool_registry = get_global_registry()
        
        # 创建模型客户端，传入工具注册器以便自动设置系统消息
        self.model_client = ModelClient(config, self.tool_registry)
        
        # 队列
        self.submission_queue = asyncio.Queue()
        
        # 统一事件处理器 - 内部管理event_queue
        self.event_handler = EventHandler()
        
        # 会话状态
        self.is_active = False
        self.current_task_id: Optional[str] = None
        self.approval_pending: Dict[str, Submission] = {}
        
        # Token统计
        self.total_token_usage = TokenUsage()
        
        # 消息压缩管理器（可选）
        self.compaction_manager: Optional[CompactionManager] = None
        if getattr(config, 'enable_compaction', False):
            # 从Config读取压缩配置
            strategy_config = {
                "prune_minimum": getattr(config, 'compaction_prune_minimum', 5000),
                "prune_protect": getattr(config, 'compaction_prune_protect', 10000),
                "protect_turns": getattr(config, 'compaction_protect_turns', 2),
                "auto_threshold": getattr(config, 'compaction_auto_threshold', 0.75),
            }
            self.compaction_manager = CompactionManager()
            self.compaction_manager.register_strategy("opencode", OpenCodeStrategy(strategy_config))
            self.compaction_manager.set_strategy("opencode")
    
    
    async def start(self):
        """启动会话"""
        self.is_active = True
        
        # 发送会话配置事件
        await self.event_handler.emit(self.session_id, EventMsg("session_configured", {
            "session_id": self.session_id,
            "model": self.config.model,
            "cwd": str(self.config.cwd)
        }))
    
    async def stop(self):
        """停止会话"""
        self.is_active = False
        
        # 发送会话结束事件
        await self.event_handler.emit(self.session_id, EventMsg("shutdown_complete", {}))
    
    async def submit_operation(self, op: Op) -> str:
        """提交操作"""
        submission = Submission.create(op)
        await self.submission_queue.put(submission)
        return submission.id
    
    async def get_next_event(self) -> Optional[Event]:
        """获取下一个事件"""
        return await self.event_handler.get_next_event()
    
    async def process_submissions(self):
        """处理提交队列"""
        while self.is_active:
            try:
                submission = await asyncio.wait_for(
                    self.submission_queue.get(), timeout=0.1
                )
                await self._handle_submission(submission)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                submission_id = submission.id if 'submission' in locals() else "unknown"
                await self.event_handler.emit_error(submission_id, f"处理提交时出错: {str(e)}")
    
    async def _handle_submission(self, submission: Submission):
        """处理单个提交"""
        op = submission.op
        
        if op.type == "user_input":
            await self._handle_user_input(submission)
        elif op.type == "interrupt":
            await self._handle_interrupt(submission)
        elif op.type == "exec_approval":
            await self._handle_exec_approval(submission)
        else:
            await self.event_handler.emit_error(submission.id, f"未知操作类型: {op.type}")
    
    async def _handle_user_input(self, submission: Submission):
        """处理用户输入 - 使用AgentTurn实现ReAct循环"""
        op = submission.op
        
        # 发送任务开始事件
        await self.event_handler.emit_task_started(submission.id)
        
        # 添加用户消息到对话历史
        if op.items:
            user_text = " ".join(item.text for item in op.items if item.text)
            self.model_client.add_user_message(user_text)
            
            # 发送用户消息事件
            await self.event_handler.emit_user_message(submission.id, user_text)
        
        # 创建AgentTurn实例
        from .agent_turn import AgentTurn
        agent_turn = AgentTurn(
            model_client=self.model_client,
            tool_registry=self.tool_registry,
            event_handler=self.event_handler,
            session_id=self.session_id
        )
        
        # ReAct 循环：持续对话直到任务完成
        max_turns = self.config.max_turns  # 防止无限循环
        turn_count = 0
        last_agent_message = None
        
        while turn_count < max_turns:
            try:
                # 执行一个AgentTurn
                turn_result = await agent_turn.execute_turn(submission.id)
                
                # 更新token使用统计
                if turn_result.token_usage:
                    self._update_token_usage(turn_result.token_usage)
                
                # 记录最后的agent消息内容（assistant消息已在AgentTurn中添加）
                if turn_result.text_content:
                    last_agent_message = turn_result.text_content
                
                # 如果没有工具调用，任务完成
                if not turn_result.has_tool_calls():
                    break
                
                # 每轮后检查并执行消息压缩
                await self._check_and_compact(submission.id)
                
                # 继续下一轮对话
                turn_count += 1
                
            except Exception as e:
                await self.event_handler.emit_error(submission.id, f"AgentTurn执行失败: {str(e)}")
                break
        
        # 检查是否达到最大轮次
        if turn_count >= max_turns:
            await self.event_handler.emit_error(
                submission.id, 
                f"任务执行达到最大轮次限制 ({max_turns})，可能存在循环"
            )
        
        # 发送任务完成事件
        await self.event_handler.emit_task_complete(
            submission.id, 
            last_agent_message or "任务已完成"
        )
    
    
    async def _handle_interrupt(self, submission: Submission):
        """处理中断"""
        self.current_task_id = None
        
        await self.event_handler.emit(submission.id, EventMsg("turn_aborted", {"reason": "interrupted"}))
    
    async def _handle_exec_approval(self, submission: Submission):
        """处理执行批准 - 委托给当前的AgentTurn处理"""
        op = submission.op
        decision = op.decision
        call_id = getattr(op, 'call_id', None)
        
        if not call_id:
            await self.event_handler.emit_error(submission.id, "批准请求缺少call_id")
            return
        
        # 注意：这里需要访问当前活跃的AgentTurn实例
        # 为简化实现，我们暂时保留原有的approval_pending机制
        # 在实际使用中，可能需要更复杂的状态管理
        
        approved = decision in ["approved", "approved_for_session"]
        
        # 发送批准决定事件
        await self.event_handler.emit(submission.id, EventMsg("approval_decision", {
            "call_id": call_id,
            "decision": decision,
            "approved": approved
        }))
    
    def _update_token_usage(self, usage: TokenUsage):
        """更新token使用统计"""
        self.total_token_usage.input_tokens += usage.input_tokens
        self.total_token_usage.output_tokens += usage.output_tokens
        self.total_token_usage.total_tokens += usage.total_tokens
        
        # 发送token统计事件
        asyncio.create_task(self.event_handler.emit(
            self.session_id, 
            EventMsg.token_count(self.total_token_usage)
        ))
    
    
    async def _check_and_compact(self, submission_id: str):
        """检查并执行消息压缩"""
        if not self.compaction_manager:
            return
        
        try:
            messages = [msg.to_dict() for msg in self.model_client.conversation_history]
            current_tokens = sum(len(str(msg.get("content", ""))) // 4 for msg in messages)
            
            context = CompactionContext(
                messages=messages,
                current_tokens=current_tokens,
                max_tokens=getattr(self.config, 'max_context_tokens', 128000),
                model_name=self.config.model,
                session_id=self.session_id,
                model_client=self.model_client
            )
            
            result = await self.compaction_manager.check_and_compact(context)
            
            if result and result.success:
                self.model_client.conversation_history = [
                    Message.from_dict(msg) for msg in result.new_messages
                ]
                
                await self.event_handler.emit(submission_id, EventMsg("compaction_complete", {
                    "removed_count": result.removed_count,
                    "tokens_saved": result.tokens_saved,
                    "strategy": result.strategy_name
                }))
        
        except Exception as e:
            # 压缩失败不应影响正常流程，只记录日志
            logger.warning(f"消息压缩失败: {e}")
