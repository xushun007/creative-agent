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


def validate_agent_config(agent_dict: dict) -> bool:
    """验证 agent 配置是否有效
    
    Args:
        agent_dict: Agent 配置字典
        
    Returns:
        是否有效
    """
    required_fields = ["description", "mode", "system_prompt", "allowed_tools"]
    
    for field in required_fields:
        if field not in agent_dict:
            logger.error(f"Agent 配置缺少必需字段: {field}")
            return False
    
    # 验证 mode
    if agent_dict["mode"] not in ["primary", "subagent"]:
        logger.error(f"无效的 mode: {agent_dict['mode']}")
        return False
    
    # 验证 allowed_tools
    if not isinstance(agent_dict["allowed_tools"], list):
        logger.error(f"allowed_tools 必须是列表")
        return False
    
    if not agent_dict["allowed_tools"]:
        logger.error(f"allowed_tools 不能为空")
        return False
    
    return True


def merge_agent_configs(base: AgentInfo, override: dict) -> AgentInfo:
    """合并 agent 配置
    
    Args:
        base: 基础 agent 配置
        override: 覆盖的配置字典
        
    Returns:
        合并后的 AgentInfo
    """
    return AgentInfo(
        name=base.name,
        description=override.get("description", base.description),
        mode=override.get("mode", base.mode),
        system_prompt=override.get("system_prompt", base.system_prompt),
        allowed_tools=override.get("allowed_tools", base.allowed_tools),
        max_turns=override.get("max_turns", base.max_turns),
        model_override=override.get("model_override", base.model_override),
        native=base.native,  # 保持 native 状态
        hidden=override.get("hidden", base.hidden),
        metadata={**base.metadata, **override.get("metadata", {})},
    )
