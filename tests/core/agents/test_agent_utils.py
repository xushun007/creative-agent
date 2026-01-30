#!/usr/bin/env python3
"""Agent 工具函数测试"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

from core.agents import (
    AgentInfo,
    AgentRegistry,
    create_agent_tool_registry,
    get_agent_tool_names,
    validate_agent_config,
    merge_agent_configs,
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
    
    def test_validate_agent_config_valid(self):
        """测试验证有效配置"""
        config = {
            "description": "测试",
            "mode": "subagent",
            "system_prompt": "提示",
            "allowed_tools": ["read"],
        }
        
        self.assertTrue(validate_agent_config(config))
    
    def test_validate_agent_config_missing_field(self):
        """测试验证缺少必需字段的配置"""
        config = {
            "description": "测试",
            "mode": "subagent",
            # 缺少 system_prompt 和 allowed_tools
        }
        
        self.assertFalse(validate_agent_config(config))
    
    def test_validate_agent_config_invalid_mode(self):
        """测试验证无效的 mode"""
        config = {
            "description": "测试",
            "mode": "invalid_mode",
            "system_prompt": "提示",
            "allowed_tools": ["read"],
        }
        
        self.assertFalse(validate_agent_config(config))
    
    def test_validate_agent_config_empty_tools(self):
        """测试验证空工具列表"""
        config = {
            "description": "测试",
            "mode": "subagent",
            "system_prompt": "提示",
            "allowed_tools": [],  # 空列表
        }
        
        self.assertFalse(validate_agent_config(config))
    
    def test_merge_agent_configs(self):
        """测试合并配置"""
        base = AgentInfo(
            name="test",
            description="原始描述",
            mode="primary",
            allowed_tools=["read"],
            max_turns=10,
        )
        
        override = {
            "description": "新描述",
            "max_turns": 20,
        }
        
        merged = merge_agent_configs(base, override)
        
        self.assertEqual(merged.description, "新描述")
        self.assertEqual(merged.max_turns, 20)
        # 未覆盖的字段保持原值
        self.assertEqual(merged.mode, "primary")
        self.assertEqual(merged.allowed_tools, ["read"])


if __name__ == '__main__':
    unittest.main()
