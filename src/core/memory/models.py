"""记忆系统数据模型"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


@dataclass
class MemoryMessage:
    """记忆系统中的消息（兼容 ModelClient.Message）"""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        d = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.metadata:
            d.update(self.metadata)
            
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryMessage":
        """从字典反序列化"""
        # 提取核心字段
        timestamp_str = data.get("timestamp")
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
        
        # 提取元数据（排除核心字段）
        excluded_keys = {"role", "content", "timestamp", "tool_calls", "tool_call_id"}
        metadata = {k: v for k, v in data.items() if k not in excluded_keys}
        
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=timestamp,
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            metadata=metadata
        )
    
    @classmethod
    def from_model_message(cls, msg: Any, timestamp: Optional[datetime] = None) -> "MemoryMessage":
        """从 ModelClient.Message 转换"""
        return cls(
            role=msg.role,
            content=msg.content,
            timestamp=timestamp or datetime.now(),
            tool_calls=msg.tool_calls,
            tool_call_id=msg.tool_call_id,
            metadata=getattr(msg, 'metadata', {})
        )
    
    def to_model_message(self):
        """转换为 ModelClient.Message"""
        from ..model_client import Message
        return Message(
            role=self.role,
            content=self.content,
            tool_calls=self.tool_calls,
            tool_call_id=self.tool_call_id,
            metadata=self.metadata
        )


class RolloutType(str, Enum):
    """Rollout 文件中的记录类型"""
    SESSION_META = "session_meta"
    MESSAGE = "message"
    COMPACTED = "compacted"


@dataclass
class SessionMeta:
    """会话元数据"""
    session_id: str
    created_at: datetime
    cwd: str
    model: str = "unknown"
    user_instructions: Optional[str] = None
    project_docs: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "cwd": self.cwd,
            "model": self.model,
            "user_instructions": self.user_instructions,
            "project_docs": self.project_docs
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMeta":
        created_at_str = data.get("created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.now()
        
        return cls(
            session_id=data["session_id"],
            created_at=created_at,
            cwd=data["cwd"],
            model=data.get("model", "unknown"),
            user_instructions=data.get("user_instructions"),
            project_docs=data.get("project_docs")
        )


@dataclass 
class CompactedMarker:
    """压缩标记"""
    summary: str
    original_count: int  # 压缩前的消息数量
    tokens_saved: int = 0  # 节省的 token 数
    strategy: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "original_count": self.original_count,
            "tokens_saved": self.tokens_saved,
            "strategy": self.strategy
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompactedMarker":
        return cls(
            summary=data["summary"],
            original_count=data.get("original_count", 0),
            tokens_saved=data.get("tokens_saved", 0),
            strategy=data.get("strategy", "unknown")
        )


@dataclass
class RolloutLine:
    """Rollout 文件的单行记录"""
    timestamp: datetime
    type: RolloutType
    data: Union[SessionMeta, MemoryMessage, CompactedMarker]
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data_dict = self.data.to_dict() if hasattr(self.data, "to_dict") else self.data.__dict__
        
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.type.value,
            "data": data_dict
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RolloutLine":
        """从字典反序列化"""
        timestamp = datetime.fromisoformat(d["timestamp"])
        rollout_type = RolloutType(d["type"])
        
        # 根据类型反序列化 data
        if rollout_type == RolloutType.SESSION_META:
            data = SessionMeta.from_dict(d["data"])
        elif rollout_type == RolloutType.MESSAGE:
            data = MemoryMessage.from_dict(d["data"])
        elif rollout_type == RolloutType.COMPACTED:
            data = CompactedMarker.from_dict(d["data"])
        else:
            raise ValueError(f"Unknown rollout type: {rollout_type}")
        
        return cls(
            timestamp=timestamp,
            type=rollout_type,
            data=data
        )

