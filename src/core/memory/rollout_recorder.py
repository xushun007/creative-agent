"""Rollout 持久化记录器"""

import json
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from .models import (
    MemoryMessage,
    RolloutType,
    SessionMeta,
    CompactedMarker,
    RolloutLine
)

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class RolloutRecorder:
    """JSONL 格式的会话记录器
    
    负责：
    - 写入会话元数据、消息、压缩标记到 JSONL 文件
    - 从 JSONL 文件加载会话历史
    - 支持追加模式（恢复会话时）
    """
    
    def __init__(self, rollout_path: Path, session_id: str):
        """
        Args:
            rollout_path: rollout 文件路径
            session_id: 会话 ID
        """
        self.rollout_path = Path(rollout_path)
        self.session_id = session_id
        self._ensure_directory()
    
    def _ensure_directory(self):
        """确保目录存在"""
        self.rollout_path.parent.mkdir(parents=True, exist_ok=True)
    
    def write_session_meta(self, meta: SessionMeta) -> None:
        """写入会话元数据（首行）
        
        Args:
            meta: 会话元数据
        """
        line = RolloutLine(
            timestamp=datetime.now(),
            type=RolloutType.SESSION_META,
            data=meta
        )
        self._append_line(line)
        logger.info(f"写入会话元数据: session_id={meta.session_id}, cwd={meta.cwd}")
    
    def write_message(self, message: MemoryMessage) -> None:
        """写入消息
        
        Args:
            message: 内存消息
        """
        line = RolloutLine(
            timestamp=datetime.now(),
            type=RolloutType.MESSAGE,
            data=message
        )
        self._append_line(line)
    
    def write_compacted_marker(self, marker: CompactedMarker) -> None:
        """写入压缩标记
        
        Args:
            marker: 压缩标记
        """
        line = RolloutLine(
            timestamp=datetime.now(),
            type=RolloutType.COMPACTED,
            data=marker
        )
        self._append_line(line)
        logger.info(f"写入压缩标记: 压缩 {marker.original_count} 条消息, 节省 {marker.tokens_saved} tokens")
    
    def _append_line(self, line: RolloutLine) -> None:
        """追加一行到文件
        
        Args:
            line: Rollout 行对象
        """
        try:
            with open(self.rollout_path, "a", encoding="utf-8") as f:
                json_str = json.dumps(line.to_dict(), ensure_ascii=False)
                f.write(json_str + "\n")
        except Exception as e:
            logger.error(f"写入 rollout 失败: {e}")
            raise
    
    @classmethod
    def load_history(cls, rollout_path: Path) -> Tuple[SessionMeta, List[MemoryMessage]]:
        """从文件加载历史
        
        Args:
            rollout_path: rollout 文件路径
        
        Returns:
            (会话元数据, 消息列表) 元组
        
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误或缺少会话元数据
        """
        rollout_path = Path(rollout_path)
        
        if not rollout_path.exists():
            raise FileNotFoundError(f"Rollout 文件不存在: {rollout_path}")
        
        session_meta: Optional[SessionMeta] = None
        messages: List[MemoryMessage] = []
        
        with open(rollout_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    rollout_line = RolloutLine.from_dict(data)
                    
                    if rollout_line.type == RolloutType.SESSION_META:
                        session_meta = rollout_line.data
                        logger.info(f"加载会话元数据: {session_meta.session_id}")
                    
                    elif rollout_line.type == RolloutType.MESSAGE:
                        messages.append(rollout_line.data)
                    
                    elif rollout_line.type == RolloutType.COMPACTED:
                        # 遇到压缩标记：清空之前的消息，只保留压缩摘要
                        marker: CompactedMarker = rollout_line.data
                        logger.info(f"遇到压缩标记: 原始 {marker.original_count} 条消息")
                        
                        # 清空旧消息，只保留系统消息和压缩摘要
                        system_msgs = [m for m in messages if m.role == "system"]
                        messages = system_msgs
                        
                        # 添加压缩摘要作为系统消息
                        summary_msg = MemoryMessage(
                            role="system",
                            content=f"[压缩摘要 - 原 {marker.original_count} 条消息]\n{marker.summary}",
                            timestamp=rollout_line.timestamp,
                            metadata={
                                "compressed": True,
                                "original_count": marker.original_count,
                                "tokens_saved": marker.tokens_saved,
                                "strategy": marker.strategy
                            }
                        )
                        messages.append(summary_msg)
                
                except json.JSONDecodeError as e:
                    logger.warning(f"解析第 {line_num} 行失败: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"处理第 {line_num} 行时出错: {e}")
                    continue
        
        if session_meta is None:
            raise ValueError(f"未找到会话元数据: {rollout_path}")
        
        logger.info(f"加载完成: {len(messages)} 条消息")
        return session_meta, messages
    
    @classmethod
    def list_sessions(cls, session_dir: Path) -> List[Tuple[Path, SessionMeta]]:
        """列出目录中的所有会话
        
        Args:
            session_dir: 会话目录
        
        Returns:
            [(rollout_path, session_meta), ...] 列表
        """
        session_dir = Path(session_dir)
        if not session_dir.exists():
            return []
        
        sessions = []
        for rollout_path in session_dir.glob("rollout-*.jsonl"):
            try:
                # 只读取第一行获取元数据
                with open(rollout_path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        rollout_line = RolloutLine.from_dict(data)
                        if rollout_line.type == RolloutType.SESSION_META:
                            sessions.append((rollout_path, rollout_line.data))
            except Exception as e:
                logger.warning(f"读取会话文件失败 {rollout_path}: {e}")
                continue
        
        # 按创建时间排序
        sessions.sort(key=lambda x: x[1].created_at, reverse=True)
        return sessions

