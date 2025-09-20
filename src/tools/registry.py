"""工具注册工厂 - 管理和提供所有可用工具"""

from typing import Dict, List, Type, Optional, Any, Set
from dataclasses import dataclass
import inspect
import logging
from .base_tool import BaseTool, ToolContext, ToolResult
from .bash import BashTool
from .edit_tool import EditTool
from .multi_edit_tool import MultiEditTool
from .file_tools import ReadTool, WriteTool
from .todo import TodoWriteTool, TodoReadTool
from .task_tool import TaskTool
from .web_tools import WebFetchTool, WebSearchTool
from .glob_tool import GlobTool
from .grep_tool import GrepTool
from .list_tool import ListTool


logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """工具信息"""
    id: str
    name: str
    description: str
    tool_class: Type[BaseTool]
    parameters: Dict[str, Any]
    enabled: bool = True


class ToolRegistry:
    """工具注册工厂 - 管理所有可用工具的注册、创建和管理"""
    
    # 默认工具列表
    DEFAULT_TOOLS: List[Type[BaseTool]] = [
        BashTool,
        EditTool,
        MultiEditTool,
        ReadTool,
        WriteTool,
        TodoWriteTool,
        TodoReadTool,
        TaskTool,
        WebFetchTool,
        WebSearchTool,
        GlobTool,
        GrepTool,
        ListTool,
    ]
    
    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, ToolInfo] = {}
        self._instances: Dict[str, BaseTool] = {}
        self._load_default_tools()
    
    def _load_default_tools(self) -> None:
        """加载默认工具"""
        for tool_class in self.DEFAULT_TOOLS:
            try:
                self.register_tool(tool_class)
            except Exception as e:
                logger.warning(f"Failed to register default tool {tool_class.__name__}: {e}")
    
    def register_tool(self, tool_class: Type[BaseTool], enabled: bool = True) -> bool:
        """
        注册工具类
        
        Args:
            tool_class: 工具类
            enabled: 是否启用
            
        Returns:
            bool: 注册是否成功
        """
        try:
            # 验证工具类
            if not issubclass(tool_class, BaseTool):
                raise ValueError(f"Tool class {tool_class.__name__} must inherit from BaseTool")
            
            # 创建临时实例以获取工具信息
            temp_instance = tool_class()
            tool_id = temp_instance.name
            
            # 检查是否已存在
            if tool_id in self._tools:
                logger.warning(f"Tool {tool_id} already registered, replacing...")
            
            # 获取参数模式
            parameters = temp_instance.get_parameters_schema()
            
            # 创建工具信息
            tool_info = ToolInfo(
                id=tool_id,
                name=temp_instance.name,
                description=temp_instance.description,
                tool_class=tool_class,
                parameters=parameters,
                enabled=enabled
            )
            
            # 注册工具
            self._tools[tool_id] = tool_info
            
            # 清理临时实例缓存（如果存在）
            if tool_id in self._instances:
                del self._instances[tool_id]
            
            logger.info(f"Successfully registered tool: {tool_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register tool {tool_class.__name__}: {e}")
            return False
    
    def unregister_tool(self, tool_id: str) -> bool:
        """
        注销工具
        
        Args:
            tool_id: 工具ID
            
        Returns:
            bool: 注销是否成功
        """
        if tool_id not in self._tools:
            logger.warning(f"Tool {tool_id} not found in registry")
            return False
        
        try:
            # 删除工具信息
            del self._tools[tool_id]
            
            # 删除实例缓存
            if tool_id in self._instances:
                del self._instances[tool_id]
            
            logger.info(f"Successfully unregistered tool: {tool_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister tool {tool_id}: {e}")
            return False
    
    def get_tool_info(self, tool_id: str) -> Optional[ToolInfo]:
        """
        获取工具信息
        
        Args:
            tool_id: 工具ID
            
        Returns:
            Optional[ToolInfo]: 工具信息，如果不存在返回None
        """
        return self._tools.get(tool_id)
    
    def get_tool_instance(self, tool_id: str) -> Optional[BaseTool]:
        """
        获取工具实例（单例模式）
        
        Args:
            tool_id: 工具ID
            
        Returns:
            Optional[BaseTool]: 工具实例，如果不存在返回None
        """
        if tool_id not in self._tools:
            return None
        
        # 如果已有缓存实例，直接返回
        if tool_id in self._instances:
            return self._instances[tool_id]
        
        try:
            # 创建新实例
            tool_info = self._tools[tool_id]
            instance = tool_info.tool_class()
            
            # 缓存实例
            self._instances[tool_id] = instance
            
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create tool instance {tool_id}: {e}")
            return None
    
    def create_tool_instance(self, tool_id: str) -> Optional[BaseTool]:
        """
        创建工具实例（每次创建新实例）
        
        Args:
            tool_id: 工具ID
            
        Returns:
            Optional[BaseTool]: 新的工具实例，如果不存在返回None
        """
        if tool_id not in self._tools:
            return None
        
        try:
            tool_info = self._tools[tool_id]
            return tool_info.tool_class()
        except Exception as e:
            logger.error(f"Failed to create new tool instance {tool_id}: {e}")
            return None
    
    def list_tools(self, enabled_only: bool = False) -> List[ToolInfo]:
        """
        列出所有工具
        
        Args:
            enabled_only: 是否只返回启用的工具
            
        Returns:
            List[ToolInfo]: 工具信息列表
        """
        tools = list(self._tools.values())
        if enabled_only:
            tools = [tool for tool in tools if tool.enabled]
        return sorted(tools, key=lambda x: x.id)
    
    def get_tool_ids(self, enabled_only: bool = False) -> List[str]:
        """
        获取所有工具ID
        
        Args:
            enabled_only: 是否只返回启用的工具
            
        Returns:
            List[str]: 工具ID列表
        """
        tools = self.list_tools(enabled_only)
        return [tool.id for tool in tools]
    
    def enable_tool(self, tool_id: str) -> bool:
        """
        启用工具
        
        Args:
            tool_id: 工具ID
            
        Returns:
            bool: 操作是否成功
        """
        if tool_id not in self._tools:
            return False
        
        self._tools[tool_id].enabled = True
        logger.info(f"Enabled tool: {tool_id}")
        return True
    
    def disable_tool(self, tool_id: str) -> bool:
        """
        禁用工具
        
        Args:
            tool_id: 工具ID
            
        Returns:
            bool: 操作是否成功
        """
        if tool_id not in self._tools:
            return False
        
        self._tools[tool_id].enabled = False
        logger.info(f"Disabled tool: {tool_id}")
        return True
    
    def is_tool_enabled(self, tool_id: str) -> bool:
        """
        检查工具是否启用
        
        Args:
            tool_id: 工具ID
            
        Returns:
            bool: 工具是否启用
        """
        tool_info = self._tools.get(tool_id)
        return tool_info.enabled if tool_info else False
    
    def get_tools_dict(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取工具字典格式列表（用于API返回）
        
        Args:
            enabled_only: 是否只返回启用的工具
            
        Returns:
            List[Dict[str, Any]]: 工具字典列表
        """
        tools = self.list_tools(enabled_only)
        return [
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "enabled": tool.enabled
            }
            for tool in tools
        ]
    
    async def execute_tool(self, tool_id: str, params: Dict[str, Any], context: ToolContext) -> Optional[ToolResult]:
        """
        执行工具
        
        Args:
            tool_id: 工具ID
            params: 工具参数
            context: 执行上下文
            
        Returns:
            Optional[ToolResult]: 执行结果，如果工具不存在或执行失败返回None
        """
        # 检查工具是否存在和启用
        if not self.is_tool_enabled(tool_id):
            logger.error(f"Tool {tool_id} is not available or disabled")
            return None
        
        # 获取工具实例
        tool = self.get_tool_instance(tool_id)
        if not tool:
            logger.error(f"Failed to get tool instance: {tool_id}")
            return None
        
        try:
            # 执行工具
            result = await tool.execute(params, context)
            return result
        except Exception as e:
            logger.error(f"Failed to execute tool {tool_id}: {e}")
            return None
    
    def clear_cache(self) -> None:
        """清理工具实例缓存"""
        self._instances.clear()
        logger.info("Tool instance cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取注册表统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        total_tools = len(self._tools)
        enabled_tools = len([t for t in self._tools.values() if t.enabled])
        cached_instances = len(self._instances)
        
        return {
            "total_tools": total_tools,
            "enabled_tools": enabled_tools,
            "disabled_tools": total_tools - enabled_tools,
            "cached_instances": cached_instances,
            "tool_ids": list(self._tools.keys())
        }
    
    def validate_tool_params(self, tool_id: str, params: Dict[str, Any]) -> bool:
        """
        验证工具参数
        
        Args:
            tool_id: 工具ID
            params: 参数
            
        Returns:
            bool: 参数是否有效
        """
        tool = self.get_tool_instance(tool_id)
        if not tool:
            return False
        
        try:
            return tool.validate_parameters(params)
        except Exception as e:
            logger.error(f"Failed to validate parameters for tool {tool_id}: {e}")
            return False


# 全局工具注册表实例
_global_registry: Optional[ToolRegistry] = None


def get_global_registry() -> ToolRegistry:
    """获取全局工具注册表实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_global_registry() -> None:
    """重置全局工具注册表（主要用于测试）"""
    global _global_registry
    _global_registry = None
