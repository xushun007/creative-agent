"""压缩策略基础接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class CompactionContext:
    """压缩上下文"""
    messages: List[Dict[str, Any]]
    current_tokens: int
    max_tokens: int
    model_name: str
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    model_client: Optional[Any] = None  # LLM客户端，用于生成摘要


@dataclass
class CompactResult:
    """压缩结果"""
    success: bool
    new_messages: List[Dict[str, Any]]
    removed_count: int
    tokens_saved: int
    strategy_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class StrategyMetadata:
    """策略元数据"""
    name: str
    version: str
    description: str
    author: str = "Creative Agent Team"


class CompactionStrategy(ABC):
    """压缩策略接口"""
    
    @abstractmethod
    def should_compact(self, context: CompactionContext) -> bool:
        pass
    
    @abstractmethod
    async def compact(self, context: CompactionContext, config: Optional[Dict[str, Any]] = None) -> CompactResult:
        pass
    
    @abstractmethod
    def get_metadata(self) -> StrategyMetadata:
        pass
