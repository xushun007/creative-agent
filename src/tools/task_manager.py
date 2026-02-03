"""Task 管理器 - 管理子代理配置和会话"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SubagentConfig:
    """子代理配置"""
    name: str                           # 代理名称，如 "plan", "general", "explore"
    description: str                    # 代理描述
    system_prompt: str                  # 子代理专用的系统提示词
    allowed_tools: List[str]            # 允许使用的工具列表
    max_turns: int = 10                 # 最大推理轮次
    temperature: float = 0.7            # LLM 温度参数
    model_override: Optional[str] = None  # 可选的模型覆盖


@dataclass
class SubagentSession:
    """子代理会话记录"""
    id: str                             # 会话ID
    parent_session_id: str              # 父会话ID
    subagent_type: str                  # 子代理类型
    task_description: str               # 任务描述
    status: str                         # running, completed, failed, timeout, cancelled
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[str] = None        # 子代理返回的结果
    error: Optional[str] = None         # 错误信息
    metadata: Dict = field(default_factory=dict)  # 额外元数据


class TaskManager:
    """任务管理器 - 单例模式"""
    
    _instance: Optional['TaskManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化任务管理器"""
        # 避免重复初始化
        if self._initialized:
            return
        
        self._subagents: Dict[str, SubagentConfig] = {}
        self._sessions: Dict[str, SubagentSession] = {}
        self._initialized = True
    
    def register_subagent(self, config: SubagentConfig) -> None:
        """注册子代理配置
        
        Args:
            config: 子代理配置
        """
        if config.name in self._subagents:
            # 避免重复注册（允许覆盖）
            pass
        self._subagents[config.name] = config
    
    def get_subagent(self, name: str) -> Optional[SubagentConfig]:
        """获取子代理配置
        
        Args:
            name: 子代理名称
            
        Returns:
            子代理配置，如果不存在返回 None
        """
        return self._subagents.get(name)
    
    def list_subagents(self) -> List[SubagentConfig]:
        """列出所有注册的子代理
        
        Returns:
            子代理配置列表
        """
        return list(self._subagents.values())
    
    def create_session(
        self,
        parent_session_id: str,
        subagent_type: str,
        task_description: str
    ) -> SubagentSession:
        """创建子代理会话
        
        Args:
            parent_session_id: 父会话ID
            subagent_type: 子代理类型
            task_description: 任务描述
            
        Returns:
            创建的子代理会话
        """
        session_id = f"task_{uuid.uuid4().hex[:8]}"
        session = SubagentSession(
            id=session_id,
            parent_session_id=parent_session_id,
            subagent_type=subagent_type,
            task_description=task_description,
            status="running",
            created_at=datetime.now()
        )
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[SubagentSession]:
        """获取子代理会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            子代理会话，如果不存在返回 None
        """
        return self._sessions.get(session_id)
    
    def update_session_status(
        self,
        session_id: str,
        status: str,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """更新子代理会话状态
        
        Args:
            session_id: 会话ID
            status: 新状态
            result: 可选的结果
            error: 可选的错误信息
        """
        session = self._sessions.get(session_id)
        if session:
            session.status = status
            if status in ("completed", "failed", "timeout", "cancelled"):
                session.completed_at = datetime.now()
            if result is not None:
                session.result = result
            if error is not None:
                session.error = error
    
    def list_sessions(self, parent_session_id: Optional[str] = None) -> List[SubagentSession]:
        """列出会话
        
        Args:
            parent_session_id: 可选的父会话ID过滤
            
        Returns:
            会话列表
        """
        if parent_session_id:
            return [
                session for session in self._sessions.values()
                if session.parent_session_id == parent_session_id
            ]
        return list(self._sessions.values())
    
    def clear_sessions(self) -> None:
        """清空所有会话记录（主要用于测试）"""
        self._sessions.clear()
