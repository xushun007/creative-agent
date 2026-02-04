#!/usr/bin/env python3
"""Agent 工具函数测试"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

from creative_agent.core.agents import (
    AgentInfo,
    AgentRegistry,
    create_agent_tool_registry,
    get_agent_tool_names,
)


class TestAgentUtils(unittest.TestCase):
    """Agent 工具函数测试"""
    
    def setUp(self):
        """重置单例"""
        AgentRegistry.reset()
    
    def test_create_agent_tool_registry_wildcard(self):
        """测试创建工具注册表（通配符）"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            allowed_tools=["*"],
        )
        
        registry = create_agent_tool_registry(agent)
        
        # 应该包含工具（具体数量取决于全局注册表）
        tools = registry.list_tools()
        self.assertGreater(len(tools), 0)
        
        # Primary agent 应该包含 task 工具
        task_tool = registry.get_tool_instance("task")
        self.assertIsNotNone(task_tool)
    
    def test_create_agent_tool_registry_subagent_no_task(self):
        """测试 subagent 的工具注册表不含 task"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="subagent",
            allowed_tools=["*"],  # 即使是通配符
        )
        
        registry = create_agent_tool_registry(agent)
        
        # Subagent 不应该有 task 工具
        task_tool = registry.get_tool_instance("task")
        self.assertIsNone(task_tool)
    
    def test_create_agent_tool_registry_specific_tools(self):
        """测试创建工具注册表（指定工具）"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            allowed_tools=["read", "grep"],
        )
        
        registry = create_agent_tool_registry(agent)
        
        # 应该只有指定的工具
        read_tool = registry.get_tool_instance("read")
        grep_tool = registry.get_tool_instance("grep")
        write_tool = registry.get_tool_instance("write")
        
        self.assertIsNotNone(read_tool)
        self.assertIsNotNone(grep_tool)
        self.assertIsNone(write_tool)  # 未允许
    
    def test_get_agent_tool_names_wildcard(self):
        """测试获取工具名称（通配符）"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            allowed_tools=["*"],
        )
        
        tool_names = get_agent_tool_names(agent)
        
        self.assertGreater(len(tool_names), 0)
        self.assertIn("read", tool_names)
        self.assertIn("task", tool_names)  # primary 应该有
    
    def test_get_agent_tool_names_subagent_no_task(self):
        """测试 subagent 的工具名称不含 task"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="subagent",
            allowed_tools=["*"],
        )
        
        tool_names = get_agent_tool_names(agent)
        
        self.assertNotIn("task", tool_names)  # subagent 不应该有
    
    def test_get_agent_tool_names_specific(self):
        """测试获取工具名称（指定工具）"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            allowed_tools=["read", "grep", "task"],
        )
        
        tool_names = get_agent_tool_names(agent)
        
        self.assertEqual(len(tool_names), 3)
        self.assertIn("read", tool_names)
        self.assertIn("grep", tool_names)
        self.assertIn("task", tool_names)
    
if __name__ == '__main__':
    unittest.main()
