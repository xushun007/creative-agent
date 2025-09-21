"""Codex协议定义 - Python精简版本"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import json
import uuid
from datetime import datetime


class AskForApproval(Enum):
    """命令批准策略"""
    UNLESS_TRUSTED = "unless_trusted"
    ON_FAILURE = "on_failure"  
    ON_REQUEST = "on_request"
    NEVER = "never"


class SandboxPolicy(Enum):
    """沙箱执行策略"""
    DANGER_FULL_ACCESS = "danger_full_access"
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"


@dataclass
class InputItem:
    """用户输入项"""
    type: str
    text: Optional[str] = None
    image_url: Optional[str] = None
    path: Optional[Path] = None


@dataclass 
class Op:
    """操作类型"""
    type: str
    items: Optional[List[InputItem]] = None
    cwd: Optional[Path] = None
    approval_policy: Optional[AskForApproval] = None
    sandbox_policy: Optional[SandboxPolicy] = None
    model: Optional[str] = None
    id: Optional[str] = None
    decision: Optional[str] = None

    @classmethod
    def user_input(cls, text: str, cwd: Path = None) -> "Op":
        """创建用户输入操作"""
        return cls(
            type="user_input",
            items=[InputItem(type="text", text=text)],
            cwd=cwd or Path.cwd()
        )
    
    @classmethod
    def interrupt(cls) -> "Op":
        """创建中断操作"""
        return cls(type="interrupt")
    
    @classmethod
    def exec_approval(cls, submission_id: str, decision: str) -> "Op":
        """创建执行批准操作"""
        return cls(type="exec_approval", id=submission_id, decision=decision)


@dataclass
class Submission:
    """提交队列条目"""
    id: str
    op: Op
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, op: Op) -> "Submission":
        """创建新提交"""
        return cls(id=str(uuid.uuid4()), op=op)


@dataclass
class TokenUsage:
    """Token使用情况"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: Optional[int] = None

    def is_zero(self) -> bool:
        return self.total_tokens == 0


@dataclass
class EventMsg:
    """事件消息"""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def task_started(cls, model_context_window: Optional[int] = None) -> "EventMsg":
        return cls("task_started", {"model_context_window": model_context_window})
    
    @classmethod
    def task_complete(cls, last_message: Optional[str] = None) -> "EventMsg":
        return cls("task_complete", {"last_agent_message": last_message})
    
    @classmethod
    def agent_message(cls, message: str) -> "EventMsg":
        return cls("agent_message", {"message": message})
    
    @classmethod
    def user_message(cls, message: str) -> "EventMsg":
        return cls("user_message", {"message": message})
    
    @classmethod
    def exec_command_begin(cls, call_id: str, command: List[str], cwd: Path) -> "EventMsg":
        return cls("exec_command_begin", {
            "call_id": call_id,
            "command": command,
            "cwd": str(cwd)
        })
    
    @classmethod
    def exec_command_end(cls, call_id: str, stdout: str, stderr: str, exit_code: int) -> "EventMsg":
        return cls("exec_command_end", {
            "call_id": call_id,
            "stdout": stdout,
            "stderr": stderr, 
            "exit_code": exit_code
        })
    
    @classmethod
    def exec_approval_request(cls, call_id: str, command: List[str], cwd: Path, reason: Optional[str] = None) -> "EventMsg":
        return cls("exec_approval_request", {
            "call_id": call_id,
            "command": command,
            "cwd": str(cwd),
            "reason": reason
        })
    
    @classmethod
    def error(cls, message: str) -> "EventMsg":
        return cls("error", {"message": message})
    
    @classmethod
    def token_count(cls, usage: TokenUsage) -> "EventMsg":
        return cls("token_count", {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "cached_input_tokens": usage.cached_input_tokens
        })


@dataclass
class Event:
    """事件队列条目"""
    id: str
    msg: EventMsg
    timestamp: datetime = field(default_factory=datetime.now)

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps({
            "id": self.id,
            "msg": {
                "type": self.msg.type,
                **self.msg.data
            },
            "timestamp": self.timestamp.isoformat()
        }, default=str)


@dataclass
class FileChange:
    """文件变更"""
    type: str  # "add", "delete", "update"
    content: Optional[str] = None
    unified_diff: Optional[str] = None
    move_path: Optional[Path] = None


@dataclass
class ReviewDecision(Enum):
    """审查决定"""
    APPROVED = "approved"
    APPROVED_FOR_SESSION = "approved_for_session" 
    DENIED = "denied"
    ABORT = "abort"
