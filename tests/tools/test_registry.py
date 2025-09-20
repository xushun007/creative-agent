#!/usr/bin/env python3
"""ToolRegistry 单元测试"""

import unittest
import asyncio
import logging
from typing import Dict, Any

# 添加项目根目录到路径
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.registry import ToolRegistry, ToolInfo, get_global_registry, reset_global_registry
    from tools.base_tool import BaseTool, ToolContext, ToolResult
    from tools.edit_tool import EditTool
    from tools.file_tools import ReadTool, WriteTool
    from tools.bash import BashTool
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.registry import ToolRegistry, ToolInfo, get_global_registry, reset_global_registry
    from tools.base_tool import BaseTool, ToolContext, ToolResult
    from tools.edit_tool import EditTool
    from tools.file_tools import ReadTool, WriteTool
    from tools.bash import BashTool


# 测试用的自定义工具
class MockTestTool(BaseTool[Dict[str, Any]]):
    """测试用工具"""
    
    def __init__(self):
        super().__init__("test_tool", "A test tool for unit testing")
        self.execution_count = 0
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Test message"
                }
            },
            "required": ["message"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        self.execution_count += 1
        message = params.get("message", "")
        return ToolResult(
            title="Test Tool Result",
            output=f"Test executed with message: {message}",
            metadata={"execution_count": self.execution_count}
        )


class MockAnotherTestTool(BaseTool[Dict[str, Any]]):
    """另一个测试用工具"""
    
    def __init__(self):
        super().__init__("another_test", "Another test tool")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "value": {
                    "type": "integer",
                    "description": "Test value"
                }
            },
            "required": ["value"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        value = params.get("value", 0)
        return ToolResult(
            title="Another Test Result",
            output=f"Value processed: {value * 2}",
            metadata={"doubled_value": value * 2}
        )


class InvalidTool:
    """无效的工具类（不继承BaseTool）"""
    pass


class TestToolRegistry(unittest.TestCase):
    """ToolRegistry 测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.registry = ToolRegistry()
        # 清空默认工具，从干净状态开始
        self.registry._tools.clear()
        self.registry._instances.clear()
        
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 禁用日志输出以避免测试时的噪音
        logging.getLogger('tools.registry').setLevel(logging.CRITICAL)
    
    def tearDown(self):
        """测试后清理"""
        self.registry.clear_cache()
    
    def test_registry_initialization(self):
        """测试注册表初始化"""
        # 创建新的注册表应该包含默认工具
        new_registry = ToolRegistry()
        self.assertGreater(len(new_registry._tools), 0)
        
        # 检查一些预期的默认工具
        tool_ids = new_registry.get_tool_ids()
        self.assertIn("edit", tool_ids)
        self.assertIn("read", tool_ids)
        self.assertIn("write", tool_ids)
    
    def test_register_tool_success(self):
        """测试成功注册工具"""
        result = self.registry.register_tool(MockTestTool)
        self.assertTrue(result)
        
        # 检查工具是否被注册
        self.assertIn("test_tool", self.registry._tools)
        
        # 检查工具信息
        tool_info = self.registry.get_tool_info("test_tool")
        self.assertIsNotNone(tool_info)
        self.assertEqual(tool_info.id, "test_tool")
        self.assertEqual(tool_info.name, "test_tool")
        self.assertTrue(tool_info.enabled)
        self.assertEqual(tool_info.tool_class, MockTestTool)
    
    def test_register_tool_invalid_class(self):
        """测试注册无效工具类"""
        result = self.registry.register_tool(InvalidTool)
        self.assertFalse(result)
        self.assertNotIn("invalid_tool", self.registry._tools)
    
    def test_register_tool_replace_existing(self):
        """测试替换已存在的工具"""
        # 先注册一个工具
        self.registry.register_tool(MockTestTool)
        original_count = len(self.registry._tools)
        
        # 再次注册相同工具
        result = self.registry.register_tool(MockTestTool)
        self.assertTrue(result)
        self.assertEqual(len(self.registry._tools), original_count)
    
    def test_unregister_tool_success(self):
        """测试成功注销工具"""
        # 先注册工具
        self.registry.register_tool(MockTestTool)
        self.assertIn("test_tool", self.registry._tools)
        
        # 注销工具
        result = self.registry.unregister_tool("test_tool")
        self.assertTrue(result)
        self.assertNotIn("test_tool", self.registry._tools)
    
    def test_unregister_tool_not_found(self):
        """测试注销不存在的工具"""
        result = self.registry.unregister_tool("nonexistent_tool")
        self.assertFalse(result)
    
    def test_get_tool_info(self):
        """测试获取工具信息"""
        self.registry.register_tool(MockTestTool)
        
        # 获取存在的工具信息
        tool_info = self.registry.get_tool_info("test_tool")
        self.assertIsNotNone(tool_info)
        self.assertIsInstance(tool_info, ToolInfo)
        self.assertEqual(tool_info.id, "test_tool")
        
        # 获取不存在的工具信息
        tool_info = self.registry.get_tool_info("nonexistent")
        self.assertIsNone(tool_info)
    
    def test_get_tool_instance_singleton(self):
        """测试获取工具实例（单例模式）"""
        self.registry.register_tool(MockTestTool)
        
        # 第一次获取
        instance1 = self.registry.get_tool_instance("test_tool")
        self.assertIsNotNone(instance1)
        self.assertIsInstance(instance1, MockTestTool)
        
        # 第二次获取应该返回相同实例
        instance2 = self.registry.get_tool_instance("test_tool")
        self.assertIs(instance1, instance2)
        
        # 获取不存在的工具
        instance3 = self.registry.get_tool_instance("nonexistent")
        self.assertIsNone(instance3)
    
    def test_create_tool_instance_new(self):
        """测试创建工具实例（每次新建）"""
        self.registry.register_tool(MockTestTool)
        
        # 创建两个实例
        instance1 = self.registry.create_tool_instance("test_tool")
        instance2 = self.registry.create_tool_instance("test_tool")
        
        self.assertIsNotNone(instance1)
        self.assertIsNotNone(instance2)
        self.assertIsNot(instance1, instance2)  # 应该是不同的实例
        
        # 创建不存在的工具实例
        instance3 = self.registry.create_tool_instance("nonexistent")
        self.assertIsNone(instance3)
    
    def test_list_tools(self):
        """测试列出工具"""
        self.registry.register_tool(MockTestTool, enabled=True)
        self.registry.register_tool(MockAnotherTestTool, enabled=False)
        
        # 列出所有工具
        all_tools = self.registry.list_tools()
        self.assertEqual(len(all_tools), 2)
        
        # 列出启用的工具
        enabled_tools = self.registry.list_tools(enabled_only=True)
        self.assertEqual(len(enabled_tools), 1)
        self.assertEqual(enabled_tools[0].id, "test_tool")
        
        # 检查排序
        tool_ids = [tool.id for tool in all_tools]
        self.assertEqual(tool_ids, sorted(tool_ids))
    
    def test_get_tool_ids(self):
        """测试获取工具ID列表"""
        self.registry.register_tool(MockTestTool, enabled=True)
        self.registry.register_tool(MockAnotherTestTool, enabled=False)
        
        # 获取所有工具ID
        all_ids = self.registry.get_tool_ids()
        self.assertEqual(set(all_ids), {"test_tool", "another_test"})
        
        # 获取启用的工具ID
        enabled_ids = self.registry.get_tool_ids(enabled_only=True)
        self.assertEqual(enabled_ids, ["test_tool"])
    
    def test_enable_disable_tool(self):
        """测试启用/禁用工具"""
        self.registry.register_tool(MockTestTool, enabled=True)
        
        # 检查初始状态
        self.assertTrue(self.registry.is_tool_enabled("test_tool"))
        
        # 禁用工具
        result = self.registry.disable_tool("test_tool")
        self.assertTrue(result)
        self.assertFalse(self.registry.is_tool_enabled("test_tool"))
        
        # 启用工具
        result = self.registry.enable_tool("test_tool")
        self.assertTrue(result)
        self.assertTrue(self.registry.is_tool_enabled("test_tool"))
        
        # 操作不存在的工具
        result = self.registry.enable_tool("nonexistent")
        self.assertFalse(result)
        result = self.registry.disable_tool("nonexistent")
        self.assertFalse(result)
    
    def test_is_tool_enabled(self):
        """测试检查工具是否启用"""
        self.registry.register_tool(MockTestTool, enabled=True)
        self.registry.register_tool(MockAnotherTestTool, enabled=False)
        
        self.assertTrue(self.registry.is_tool_enabled("test_tool"))
        self.assertFalse(self.registry.is_tool_enabled("another_test"))
        self.assertFalse(self.registry.is_tool_enabled("nonexistent"))
    
    def test_get_tools_dict(self):
        """测试获取工具字典格式"""
        self.registry.register_tool(MockTestTool, enabled=True)
        self.registry.register_tool(MockAnotherTestTool, enabled=False)
        
        # 获取所有工具字典
        all_dicts = self.registry.get_tools_dict()
        self.assertEqual(len(all_dicts), 2)
        
        # 检查字典结构
        tool_dict = all_dicts[0]
        required_keys = {"id", "name", "description", "parameters", "enabled"}
        self.assertEqual(set(tool_dict.keys()), required_keys)
        
        # 获取启用的工具字典
        enabled_dicts = self.registry.get_tools_dict(enabled_only=True)
        self.assertEqual(len(enabled_dicts), 1)
        self.assertEqual(enabled_dicts[0]["id"], "test_tool")
    
    def test_execute_tool(self):
        """测试执行工具"""
        async def run_test():
            self.registry.register_tool(MockTestTool, enabled=True)
            
            # 执行启用的工具
            result = await self.registry.execute_tool(
                "test_tool",
                {"message": "Hello, World!"},
                self.context
            )
            
            self.assertIsNotNone(result)
            self.assertEqual(result.title, "Test Tool Result")
            self.assertIn("Hello, World!", result.output)
            
            # 执行不存在的工具
            result = await self.registry.execute_tool(
                "nonexistent",
                {},
                self.context
            )
            self.assertIsNone(result)
            
            # 执行禁用的工具
            self.registry.disable_tool("test_tool")
            result = await self.registry.execute_tool(
                "test_tool",
                {"message": "Test"},
                self.context
            )
            self.assertIsNone(result)
        
        asyncio.run(run_test())
    
    def test_clear_cache(self):
        """测试清理缓存"""
        self.registry.register_tool(MockTestTool)
        
        # 获取实例以填充缓存
        instance = self.registry.get_tool_instance("test_tool")
        self.assertIsNotNone(instance)
        self.assertEqual(len(self.registry._instances), 1)
        
        # 清理缓存
        self.registry.clear_cache()
        self.assertEqual(len(self.registry._instances), 0)
        
        # 再次获取应该创建新实例
        new_instance = self.registry.get_tool_instance("test_tool")
        self.assertIsNotNone(new_instance)
        self.assertIsNot(instance, new_instance)
    
    def test_get_statistics(self):
        """测试获取统计信息"""
        self.registry.register_tool(MockTestTool, enabled=True)
        self.registry.register_tool(MockAnotherTestTool, enabled=False)
        
        # 获取实例以填充缓存
        self.registry.get_tool_instance("test_tool")
        
        stats = self.registry.get_statistics()
        
        expected_keys = {"total_tools", "enabled_tools", "disabled_tools", "cached_instances", "tool_ids"}
        self.assertEqual(set(stats.keys()), expected_keys)
        
        self.assertEqual(stats["total_tools"], 2)
        self.assertEqual(stats["enabled_tools"], 1)
        self.assertEqual(stats["disabled_tools"], 1)
        self.assertEqual(stats["cached_instances"], 1)
        self.assertEqual(set(stats["tool_ids"]), {"test_tool", "another_test"})
    
    def test_validate_tool_params(self):
        """测试验证工具参数"""
        self.registry.register_tool(MockTestTool)
        
        # 有效参数
        valid_params = {"message": "test"}
        result = self.registry.validate_tool_params("test_tool", valid_params)
        self.assertTrue(result)
        
        # 验证不存在的工具
        result = self.registry.validate_tool_params("nonexistent", {})
        self.assertFalse(result)
    
    def test_global_registry(self):
        """测试全局注册表"""
        # 获取全局注册表
        global_reg1 = get_global_registry()
        global_reg2 = get_global_registry()
        
        # 应该返回相同实例
        self.assertIs(global_reg1, global_reg2)
        self.assertIsInstance(global_reg1, ToolRegistry)
        
        # 重置全局注册表
        reset_global_registry()
        global_reg3 = get_global_registry()
        
        # 应该是新实例
        self.assertIsNot(global_reg1, global_reg3)
    
    def test_default_tools_loading(self):
        """测试默认工具加载"""
        # 创建新注册表应该自动加载默认工具
        new_registry = ToolRegistry()
        
        # 检查是否包含预期的工具
        tool_ids = new_registry.get_tool_ids()
        expected_tools = ["edit", "multiedit", "read", "write", "bash"]
        
        for tool_id in expected_tools:
            self.assertIn(tool_id, tool_ids, f"Expected tool {tool_id} not found")
        
        # 检查工具是否可以正常获取
        for tool_id in expected_tools:
            instance = new_registry.get_tool_instance(tool_id)
            self.assertIsNotNone(instance, f"Failed to get instance for {tool_id}")
    
    def test_tool_execution_with_real_tools(self):
        """测试使用真实工具的执行"""
        async def run_test():
            # 使用包含默认工具的注册表
            registry = ToolRegistry()
            
            # 测试读取工具
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write("Hello, World!")
                temp_file = f.name
            
            try:
                result = await registry.execute_tool(
                    "read",
                    {"filePath": temp_file},
                    self.context
                )
                
                self.assertIsNotNone(result)
                self.assertIn("Hello, World!", result.output)
                
            finally:
                os.unlink(temp_file)
        
        asyncio.run(run_test())
    
    def test_concurrent_tool_access(self):
        """测试并发工具访问"""
        async def run_test():
            self.registry.register_tool(MockTestTool)
            
            # 并发获取工具实例
            tasks = []
            for i in range(10):
                task = asyncio.create_task(
                    self.registry.execute_tool(
                        "test_tool",
                        {"message": f"Message {i}"},
                        self.context
                    )
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            # 所有执行都应该成功
            for result in results:
                self.assertIsNotNone(result)
                self.assertEqual(result.title, "Test Tool Result")
        
        asyncio.run(run_test())
    
    def test_tool_info_dataclass(self):
        """测试ToolInfo数据类"""
        tool_info = ToolInfo(
            id="test_id",
            name="test_name",
            description="test_description",
            tool_class=MockTestTool,
            parameters={"test": "params"},
            enabled=True
        )
        
        self.assertEqual(tool_info.id, "test_id")
        self.assertEqual(tool_info.name, "test_name")
        self.assertEqual(tool_info.description, "test_description")
        self.assertEqual(tool_info.tool_class, MockTestTool)
        self.assertEqual(tool_info.parameters, {"test": "params"})
        self.assertTrue(tool_info.enabled)


if __name__ == "__main__":
    unittest.main()