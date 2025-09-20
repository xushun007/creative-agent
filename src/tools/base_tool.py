from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass
import json


@dataclass
class ToolContext:
    """工具执行上下文"""
    session_id: str
    message_id: str
    agent: str
    call_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


@dataclass
class ToolResult:
    """工具执行结果"""
    title: str
    output: str
    metadata: Optional[Dict[str, Any]] = None


T = TypeVar('T')


class BaseTool(ABC, Generic[T]):
    """基础工具抽象类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """获取参数模式定义"""
        pass
    
    @abstractmethod
    async def execute(self, params: T, context: ToolContext) -> ToolResult:
        """执行工具逻辑"""
        pass
    
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """验证参数是否符合模式"""
        # 这里可以实现具体的参数验证逻辑
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_parameters_schema()
        }
