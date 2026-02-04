#!/usr/bin/env python3
"""AgentInfo 数据类测试"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

from creative_agent.core.agents import AgentInfo


class TestAgentInfo(unittest.TestCase):
    """AgentInfo 数据类测试"""
    
    def test_create_agent_info(self):
        """测试创建 AgentInfo"""
        agent = AgentInfo(
            name="test",
            description="测试 agent",
            mode="primary",
            system_prompt="你是测试 agent",
            allowed_tools=["read", "write"],
            max_turns=20,
        )
        
        self.assertEqual(agent.name, "test")
        self.assertEqual(agent.description, "测试 agent")
        self.assertEqual(agent.mode, "primary")
        self.assertEqual(agent.system_prompt, "你是测试 agent")
        self.assertEqual(agent.allowed_tools, ["read", "write"])
        self.assertEqual(agent.max_turns, 20)
        self.assertTrue(agent.native)  # 默认值
        self.assertFalse(agent.hidden)  # 默认值
    
    def test_agent_info_defaults(self):
        """测试 AgentInfo 默认值"""
        agent = AgentInfo(
            name="minimal",
            description="最小配置",
            mode="subagent",
            allowed_tools=["*"],
        )
        
        self.assertEqual(agent.max_turns, 10)
        self.assertIsNone(agent.system_prompt)
        self.assertIsNone(agent.model_override)
        self.assertTrue(agent.native)
        self.assertFalse(agent.hidden)
        self.assertEqual(agent.metadata, {})
    
    def test_invalid_mode(self):
        """测试无效的 mode"""
        with self.assertRaises(ValueError) as ctx:
            AgentInfo(
                name="invalid",
                description="无效",
                mode="invalid_mode",  # 无效
                allowed_tools=["read"],
            )
        
        self.assertIn("Invalid mode", str(ctx.exception))
    
    def test_empty_name(self):
        """测试空名称"""
        with self.assertRaises(ValueError) as ctx:
            AgentInfo(
                name="",  # 空名称
                description="测试",
                mode="primary",
                allowed_tools=["read"],
            )
        
        self.assertIn("name cannot be empty", str(ctx.exception))
    
    def test_empty_allowed_tools(self):
        """测试空工具列表"""
        with self.assertRaises(ValueError) as ctx:
            AgentInfo(
                name="test",
                description="测试",
                mode="primary",
                allowed_tools=[],  # 空列表
            )
        
        self.assertIn("must have at least one allowed tool", str(ctx.exception))
    
    def test_can_use_tool_wildcard(self):
        """测试通配符工具权限"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            allowed_tools=["*"],
        )
        
        self.assertTrue(agent.can_use_tool("read"))
        self.assertTrue(agent.can_use_tool("write"))
        self.assertTrue(agent.can_use_tool("task"))
        self.assertTrue(agent.can_use_tool("any_tool"))
    
    def test_can_use_tool_specific(self):
        """测试指定工具权限"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            allowed_tools=["read", "grep"],
        )
        
        self.assertTrue(agent.can_use_tool("read"))
        self.assertTrue(agent.can_use_tool("grep"))
        self.assertFalse(agent.can_use_tool("write"))
        self.assertFalse(agent.can_use_tool("task"))
    
    def test_subagent_cannot_use_task(self):
        """测试 subagent 不能使用 task 工具"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="subagent",
            allowed_tools=["*"],  # 即使是通配符
        )
        
        self.assertTrue(agent.can_use_tool("read"))
        self.assertFalse(agent.can_use_tool("task"))  # subagent 不允许
    
    def test_to_dict(self):
        """测试序列化为字典"""
        agent = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            system_prompt="测试提示",
            allowed_tools=["read"],
            max_turns=20,
            model_override="gpt-4",
            native=False,
            hidden=True,
            metadata={"key": "value"},
        )
        
        data = agent.to_dict()
        
        self.assertEqual(data["name"], "test")
        self.assertEqual(data["description"], "测试")
        self.assertEqual(data["mode"], "primary")
        self.assertEqual(data["system_prompt"], "测试提示")
        self.assertEqual(data["allowed_tools"], ["read"])
        self.assertEqual(data["max_turns"], 20)
        self.assertEqual(data["model_override"], "gpt-4")
        self.assertFalse(data["native"])
        self.assertTrue(data["hidden"])
        self.assertEqual(data["metadata"], {"key": "value"})
    
    def test_from_dict(self):
        """测试从字典反序列化"""
        data = {
            "name": "test",
            "description": "测试",
            "mode": "subagent",
            "system_prompt": "测试提示",
            "allowed_tools": ["read", "grep"],
            "max_turns": 15,
            "model_override": "claude-3",
            "native": True,
            "hidden": False,
            "metadata": {"custom": "data"},
        }
        
        agent = AgentInfo.from_dict(data)
        
        self.assertEqual(agent.name, "test")
        self.assertEqual(agent.description, "测试")
        self.assertEqual(agent.mode, "subagent")
        self.assertEqual(agent.system_prompt, "测试提示")
        self.assertEqual(agent.allowed_tools, ["read", "grep"])
        self.assertEqual(agent.max_turns, 15)
        self.assertEqual(agent.model_override, "claude-3")
        self.assertTrue(agent.native)
        self.assertFalse(agent.hidden)
        self.assertEqual(agent.metadata, {"custom": "data"})
    
    def test_roundtrip_serialization(self):
        """测试序列化往返"""
        original = AgentInfo(
            name="test",
            description="测试",
            mode="primary",
            allowed_tools=["*"],
            max_turns=25,
        )
        
        # 序列化
        data = original.to_dict()
        
        # 反序列化
        restored = AgentInfo.from_dict(data)
        
        # 验证一致性
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.description, original.description)
        self.assertEqual(restored.mode, original.mode)
        self.assertEqual(restored.allowed_tools, original.allowed_tools)
        self.assertEqual(restored.max_turns, original.max_turns)


if __name__ == '__main__':
    unittest.main()
