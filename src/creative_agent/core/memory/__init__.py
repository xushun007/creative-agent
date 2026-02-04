"""记忆系统模块

核心组件：
- MemoryManager: 记忆管理器（运行时历史 + 持久化）
- MemoryMessage: 消息模型
- SessionMeta: 会话元数据
- RolloutRecorder: JSONL 持久化记录器
- ProjectDocLoader: 项目文档加载器

注意：Token 估算统一使用 src.core.compaction.utils.estimate_tokens
"""

from .models import (
    MemoryMessage,
    RolloutType,
    SessionMeta,
    CompactedMarker,
    RolloutLine
)
from .rollout_recorder import RolloutRecorder
from .project_doc import ProjectDocLoader
from .memory_manager import MemoryManager

__all__ = [
    "MemoryMessage",
    "RolloutType",
    "SessionMeta",
    "CompactedMarker",
    "RolloutLine",
    "RolloutRecorder",
    "ProjectDocLoader",
    "MemoryManager",
]

