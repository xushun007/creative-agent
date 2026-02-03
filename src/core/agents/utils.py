"""Agent 相关的工具函数"""

from typing import TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from tools.registry import ToolRegistry

from .info import AgentInfo

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def create_agent_tool_registry(agent: 'AgentInfo') -> 'ToolRegistry':
    """为 agent 创建过滤后的工具注册表
    
    Args:
        agent: Agent 配置信息
        
    Returns:
        过滤后的工具注册表，只包含 agent 允许的工具
    """
    from tools.registry import get_global_registry, ToolRegistry
    
    global_registry = get_global_registry()
    agent_registry = ToolRegistry()
    
    # 清空默认工具（确保只包含允许的工具）
    agent_registry._tools.clear()
    agent_registry._instances.clear()
    
    # 处理通配符
    if "*" in agent.allowed_tools:
        # 允许所有工具
        for tool_info in global_registry.list_tools():
            # Subagent 不能使用 task 工具（防止无限嵌套）
            if agent.mode == "subagent" and tool_info.name == "task":
                logger.debug(f"跳过 task 工具（subagent 不允许）")
                continue
            
            agent_registry.register_tool(tool_info.tool_class, enabled=True)
        
        logger.debug(f"Agent {agent.name}: 允许所有工具（subagent 排除 task）")
    else:
        # 只注册允许的工具
        registered_count = 0
        for tool_name in agent.allowed_tools:
            # Subagent 不能使用 task 工具
            if agent.mode == "subagent" and tool_name == "task":
                logger.warning(f"Agent {agent.name}: 忽略 task 工具（subagent 不允许）")
                continue
            
            tool_info = global_registry.get_tool_info(tool_name)
            if tool_info:
                agent_registry.register_tool(tool_info.tool_class, enabled=True)
                registered_count += 1
            else:
                logger.warning(f"Agent {agent.name}: 工具不存在: {tool_name}")
        
        logger.debug(f"Agent {agent.name}: 注册了 {registered_count}/{len(agent.allowed_tools)} 个工具")
    
    return agent_registry


def get_agent_tool_names(agent: 'AgentInfo') -> List[str]:
    """获取 agent 允许使用的工具名称列表
    
    Args:
        agent: Agent 配置信息
        
    Returns:
        工具名称列表
    """
    from tools.registry import get_global_registry
    
    if "*" in agent.allowed_tools:
        # 所有工具（subagent 排除 task）
        all_tools = [info.name for info in get_global_registry().list_tools()]
        
        if agent.mode == "subagent":
            return [t for t in all_tools if t != "task"]
        
        return all_tools
    
    # 指定的工具（subagent 排除 task）
    tools = agent.allowed_tools.copy()
    
    if agent.mode == "subagent" and "task" in tools:
        tools.remove("task")
    
    return tools
