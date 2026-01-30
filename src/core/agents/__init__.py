"""Agent 系统

Agent 系统负责管理不同类型的代理，每个代理有不同的：
- 系统提示（定义角色和行为）
- 工具权限（allowed_tools）
- 执行参数（max_turns, model_override）

架构：
- AgentInfo: 不可变的配置对象
- AgentRegistry: 单例，管理所有 agents
- Message 记录使用的 agent
- Session 创建时可以指定 parent_session_id（父子关系）

内置 Agents：
- build: 默认主代理（完整权限）
- plan: 规划主代理（只读权限）
- general: 通用子代理（编程权限，不含 task）
- explore: 探索子代理（搜索权限，不含 task）
"""

from .info import AgentInfo
from .registry import AgentRegistry
from .utils import (
    create_agent_tool_registry,
    get_agent_tool_names,
    validate_agent_config,
    merge_agent_configs,
)
from .prompts import (
    BUILD_AGENT_PROMPT,
    PLAN_AGENT_PROMPT,
    GENERAL_AGENT_PROMPT,
    EXPLORE_AGENT_PROMPT,
    get_agent_prompt,
)

__all__ = [
    # 数据类
    "AgentInfo",
    
    # 注册表
    "AgentRegistry",
    
    # 工具函数
    "create_agent_tool_registry",
    "get_agent_tool_names",
    "validate_agent_config",
    "merge_agent_configs",
    
    # 系统提示
    "BUILD_AGENT_PROMPT",
    "PLAN_AGENT_PROMPT",
    "GENERAL_AGENT_PROMPT",
    "EXPLORE_AGENT_PROMPT",
    "get_agent_prompt",
]
