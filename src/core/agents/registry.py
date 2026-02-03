"""Agent 注册表 - 单例模式

当前版本暂不支持从 .creative-agent/config.json 加载 agents 配置（保持硬编码，与 opencode 行为一致）。
"""

from typing import Dict, List, Optional, Literal

from .info import AgentInfo
from .prompts import (
    BUILD_AGENT_PROMPT,
    PLAN_AGENT_PROMPT,
    GENERAL_AGENT_PROMPT,
    EXPLORE_AGENT_PROMPT,
)

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AgentRegistry:
    """Agent 注册表（单例）
    
    管理所有可用的 agents，包括内置和自定义。
    """
    
    _instance: Optional['AgentRegistry'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return
        
        self._agents: Dict[str, AgentInfo] = {}
        self._initialized = True
        
        # 注册内置 agents
        self._register_builtin_agents()
    
    @classmethod
    def get_instance(cls) -> 'AgentRegistry':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """重置单例（主要用于测试）"""
        cls._instance = None
    
    def _register_builtin_agents(self):
        """注册内置 agents"""
        
        # 1. Build Agent (默认主代理)
        self.register(AgentInfo(
            name="build",
            description="默认主代理，具有完整的工具访问权限，可处理各类编程任务",
            mode="primary",
            system_prompt=BUILD_AGENT_PROMPT,
            allowed_tools=["*"],  # 所有工具
            max_turns=50,
            native=True,
        ))
        
        # 2. Plan Agent (规划主代理)
        self.register(AgentInfo(
            name="plan",
            description="规划模式主代理，只读权限，专注于技术方案设计和架构规划",
            mode="primary",
            system_prompt=PLAN_AGENT_PROMPT,
            allowed_tools=["read", "grep", "glob", "list"],
            max_turns=30,
            native=True,
        ))
        
        # 3. General Agent (通用子代理)
        self.register(AgentInfo(
            name="general",
            description="通用编程子代理，可执行多步骤编程任务，包括代码实现、测试和文件操作",
            mode="subagent",
            system_prompt=GENERAL_AGENT_PROMPT,
            allowed_tools=[
                "read", "write", "edit",
                "grep", "glob", "list",
                "bash", "todowrite", "todoread"
            ],
            max_turns=30,
            native=True,
        ))
        
        # 4. Explore Agent (探索子代理)
        self.register(AgentInfo(
            name="explore",
            description="代码库探索专家，快速搜索和定位代码，分析项目结构",
            mode="subagent",
            system_prompt=EXPLORE_AGENT_PROMPT,
            allowed_tools=["read", "grep", "glob", "list"],
            max_turns=30,
            native=True,
        ))
        
        logger.info(f"注册了 {len(self._agents)} 个内置 agents")
    
    def register(self, agent: AgentInfo) -> None:
        """注册 agent
        
        Args:
            agent: Agent 配置信息
            
        Raises:
            ValueError: 如果 agent 名称已存在（除非 native=False 可覆盖）
        """
        if agent.name in self._agents:
            existing = self._agents[agent.name]
            # 内置 agent 不能被覆盖（除非是重新注册内置）
            if existing.native and not agent.native:
                logger.warning(f"无法覆盖内置 agent: {agent.name}")
                return
            
            logger.info(f"覆盖 agent: {agent.name}")
        
        self._agents[agent.name] = agent
        logger.debug(f"注册 agent: {agent.name} (mode={agent.mode}, native={agent.native})")
    
    def get(self, name: str) -> Optional[AgentInfo]:
        """获取 agent
        
        Args:
            name: Agent 名称
            
        Returns:
            AgentInfo 对象，如果不存在返回 None
        """
        return self._agents.get(name)
    
    def list_agents(
        self,
        mode: Optional[Literal["primary", "subagent"]] = None,
        include_hidden: bool = False
    ) -> List[AgentInfo]:
        """列出 agents
        
        Args:
            mode: 过滤模式（primary 或 subagent）
            include_hidden: 是否包含隐藏的 agents
            
        Returns:
            AgentInfo 列表
        """
        agents = list(self._agents.values())
        
        if mode:
            agents = [a for a in agents if a.mode == mode]
        
        if not include_hidden:
            agents = [a for a in agents if not a.hidden]
        
        return agents
    
    def exists(self, name: str) -> bool:
        """检查 agent 是否存在
        
        Args:
            name: Agent 名称
            
        Returns:
            是否存在
        """
        return name in self._agents
    
    def remove(self, name: str) -> bool:
        """移除 agent
        
        Args:
            name: Agent 名称
            
        Returns:
            是否成功移除
        """
        if name not in self._agents:
            return False
        
        agent = self._agents[name]
        if agent.native:
            logger.warning(f"无法移除内置 agent: {name}")
            return False
        
        del self._agents[name]
        logger.info(f"移除 agent: {name}")
        return True
    
    def get_agent_names(self) -> List[str]:
        """获取所有 agent 名称列表"""
        return list(self._agents.keys())
    
    def __len__(self) -> int:
        """返回 agent 数量"""
        return len(self._agents)
    
    def __contains__(self, name: str) -> bool:
        """支持 'name' in registry"""
        return name in self._agents
