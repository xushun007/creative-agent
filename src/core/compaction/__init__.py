"""消息压缩模块"""

from .base import (
    CompactionStrategy,
    CompactionContext,
    CompactResult,
    StrategyMetadata,
)
from .manager import CompactionManager
from .strategies.opencode import OpenCodeStrategy

__all__ = [
    "CompactionStrategy",
    "CompactionContext",
    "CompactResult",
    "StrategyMetadata",
    "CompactionManager",
    "OpenCodeStrategy",
]

