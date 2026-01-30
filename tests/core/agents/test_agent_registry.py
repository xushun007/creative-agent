#!/usr/bin/env python3
"""AgentRegistry 单元测试"""

import unittest
import sys
import os
from pathlib import Path
import tempfile
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

from core.agents import AgentRegistry, AgentInfo


class TestAgentRegistry(unittest.TestCase):
    """AgentRegistry 单元测试"""
    
    def setUp(self):
        """每个测试前重置单例"""
        AgentRegistry.reset()
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        registry1 = AgentRegistry.get_instance()
        registry2 = AgentRegistry.get_instance()
        
        self.assertIs(registry1, registry2)
    
    def test_builtin_agents_registered(self):
        """测试内置 agents 已注册"""
        registry = AgentRegistry()
        
        # 应该有 4 个内置 agents
        self.assertEqual(len(registry), 4)
        
        # 验证每个内置 agent
        for name in ["build", "plan", "general", "explore"]:
            agent = registry.get(name)
            self.assertIsNotNone(agent, f"内置 agent {name} 应该存在")
            self.assertTrue(agent.native, f"{name} 应该是内置的")
    
    def test_get_agent(self):
        """测试获取 agent"""
        registry = AgentRegistry()
        
        # 获取存在的 agent
        build = registry.get("build")
        self.assertIsNotNone(build)
        self.assertEqual(build.name, "build")
        self.assertEqual(build.mode, "primary")
        
        # 获取不存在的 agent
        none_agent = registry.get("nonexistent")
        self.assertIsNone(none_agent)
    
    def test_list_all_agents(self):
        """测试列出所有 agents"""
        registry = AgentRegistry()
        
        agents = registry.list_agents()
        
        self.assertEqual(len(agents), 4)
        names = [a.name for a in agents]
        self.assertIn("build", names)
        self.assertIn("plan", names)
        self.assertIn("general", names)
        self.assertIn("explore", names)
    
    def test_list_by_mode(self):
        """测试按模式过滤"""
        registry = AgentRegistry()
        
        # 只列出 primary agents
        primary_agents = registry.list_agents(mode="primary")
        self.assertEqual(len(primary_agents), 2)
        names = [a.name for a in primary_agents]
        self.assertIn("build", names)
        self.assertIn("plan", names)
        
        # 只列出 subagents
        subagents = registry.list_agents(mode="subagent")
        self.assertEqual(len(subagents), 2)
        names = [a.name for a in subagents]
        self.assertIn("general", names)
        self.assertIn("explore", names)
    
    def test_register_custom_agent(self):
        """测试注册自定义 agent"""
        registry = AgentRegistry()
        
        custom_agent = AgentInfo(
            name="custom",
            description="自定义 agent",
            mode="subagent",
            allowed_tools=["read", "grep"],
            native=False,
        )
        
        registry.register(custom_agent)
        
        # 验证注册成功
        self.assertEqual(len(registry), 5)
        retrieved = registry.get("custom")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "custom")
        self.assertFalse(retrieved.native)
    
    def test_cannot_override_native_agent(self):
        """测试不能覆盖内置 agent（除非也是 native）"""
        registry = AgentRegistry()
        
        # 尝试覆盖内置 agent
        fake_build = AgentInfo(
            name="build",
            description="假的 build",
            mode="primary",
            allowed_tools=["read"],
            native=False,  # 非内置
        )
        
        registry.register(fake_build)
        
        # 应该保持原来的内置 agent
        build = registry.get("build")
        self.assertNotEqual(build.description, "假的 build")
        self.assertTrue(build.native)
    
    def test_override_custom_agent(self):
        """测试可以覆盖自定义 agent"""
        registry = AgentRegistry()
        
        # 注册自定义 agent
        custom1 = AgentInfo(
            name="custom",
            description="版本1",
            mode="subagent",
            allowed_tools=["read"],
            native=False,
        )
        registry.register(custom1)
        
        # 覆盖
        custom2 = AgentInfo(
            name="custom",
            description="版本2",
            mode="subagent",
            allowed_tools=["read", "grep"],
            native=False,
        )
        registry.register(custom2)
        
        # 验证覆盖成功
        retrieved = registry.get("custom")
        self.assertEqual(retrieved.description, "版本2")
        self.assertEqual(len(retrieved.allowed_tools), 2)
    
    def test_exists(self):
        """测试检查 agent 是否存在"""
        registry = AgentRegistry()
        
        self.assertTrue(registry.exists("build"))
        self.assertTrue(registry.exists("plan"))
        self.assertFalse(registry.exists("nonexistent"))
    
    def test_contains(self):
        """测试 in 操作符"""
        registry = AgentRegistry()
        
        self.assertIn("build", registry)
        self.assertIn("plan", registry)
        self.assertNotIn("nonexistent", registry)
    
    def test_remove_custom_agent(self):
        """测试移除自定义 agent"""
        registry = AgentRegistry()
        
        # 注册自定义 agent
        custom = AgentInfo(
            name="custom",
            description="自定义",
            mode="subagent",
            allowed_tools=["read"],
            native=False,
        )
        registry.register(custom)
        
        # 移除
        result = registry.remove("custom")
        self.assertTrue(result)
        self.assertNotIn("custom", registry)
    
    def test_cannot_remove_native_agent(self):
        """测试不能移除内置 agent"""
        registry = AgentRegistry()
        
        result = registry.remove("build")
        self.assertFalse(result)
        self.assertIn("build", registry)
    
    def test_remove_nonexistent_agent(self):
        """测试移除不存在的 agent"""
        registry = AgentRegistry()
        
        result = registry.remove("nonexistent")
        self.assertFalse(result)
    
    def test_get_agent_names(self):
        """测试获取 agent 名称列表"""
        registry = AgentRegistry()
        
        names = registry.get_agent_names()
        
        self.assertEqual(len(names), 4)
        self.assertIn("build", names)
        self.assertIn("plan", names)
        self.assertIn("general", names)
        self.assertIn("explore", names)
    
    def test_list_hidden_agents(self):
        """测试列出隐藏的 agents"""
        registry = AgentRegistry()
        
        # 注册隐藏 agent
        hidden = AgentInfo(
            name="hidden",
            description="隐藏",
            mode="primary",
            allowed_tools=["read"],
            hidden=True,
            native=False,
        )
        registry.register(hidden)
        
        # 默认不包含隐藏
        visible = registry.list_agents()
        names = [a.name for a in visible]
        self.assertNotIn("hidden", names)
        
        # 显式包含隐藏
        all_agents = registry.list_agents(include_hidden=True)
        names = [a.name for a in all_agents]
        self.assertIn("hidden", names)
    
    def test_load_from_config_custom_agent(self):
        """测试从配置文件加载自定义 agent"""
        registry = AgentRegistry()
        
        # 创建临时配置文件
        config_data = {
            "agents": {
                "debug": {
                    "description": "调试专家",
                    "mode": "subagent",
                    "system_prompt": "你是调试专家",
                    "allowed_tools": ["read", "grep", "shell"],
                    "max_turns": 12,
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            # 加载配置
            loaded = registry.load_from_config(config_path)
            
            self.assertEqual(loaded, 1)
            self.assertEqual(len(registry), 5)  # 4 内置 + 1 自定义
            
            # 验证自定义 agent
            debug = registry.get("debug")
            self.assertIsNotNone(debug)
            self.assertEqual(debug.description, "调试专家")
            self.assertEqual(debug.mode, "subagent")
            self.assertEqual(debug.max_turns, 12)
            self.assertFalse(debug.native)
        finally:
            config_path.unlink()
    
    def test_load_from_config_override_builtin(self):
        """测试从配置文件覆盖内置 agent"""
        registry = AgentRegistry()
        
        # 创建临时配置文件（覆盖 plan）
        config_data = {
            "agents": {
                "plan": {
                    "max_turns": 40,  # 覆盖默认的 30
                    "description": "自定义描述",
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            loaded = registry.load_from_config(config_path)
            
            self.assertEqual(loaded, 1)
            
            # 验证覆盖
            plan = registry.get("plan")
            self.assertEqual(plan.max_turns, 40)
            self.assertEqual(plan.description, "自定义描述")
            # 其他字段保持不变
            self.assertTrue(plan.native)
            self.assertEqual(plan.mode, "primary")
        finally:
            config_path.unlink()
    
    def test_load_from_config_disable_agent(self):
        """测试从配置文件禁用 agent"""
        registry = AgentRegistry()
        
        # 注册自定义 agent
        custom = AgentInfo(
            name="custom",
            description="自定义",
            mode="subagent",
            allowed_tools=["read"],
            native=False,
        )
        registry.register(custom)
        
        # 创建配置禁用它
        config_data = {
            "agents": {
                "custom": {
                    "disabled": True
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            loaded = registry.load_from_config(config_path)
            
            # 验证已禁用
            self.assertNotIn("custom", registry)
        finally:
            config_path.unlink()
    
    def test_load_from_nonexistent_config(self):
        """测试加载不存在的配置文件"""
        registry = AgentRegistry()
        
        nonexistent = Path("/tmp/nonexistent_config_12345.json")
        loaded = registry.load_from_config(nonexistent)
        
        self.assertEqual(loaded, 0)
        # 内置 agents 应该仍然存在
        self.assertEqual(len(registry), 4)
    
    def test_load_from_invalid_json(self):
        """测试加载无效的 JSON 文件"""
        registry = AgentRegistry()
        
        # 创建无效 JSON 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            config_path = Path(f.name)
        
        try:
            loaded = registry.load_from_config(config_path)
            
            self.assertEqual(loaded, 0)
            # 内置 agents 应该仍然存在
            self.assertEqual(len(registry), 4)
        finally:
            config_path.unlink()
    
    def test_load_incomplete_agent_config(self):
        """测试加载不完整的 agent 配置"""
        registry = AgentRegistry()
        
        # 创建不完整配置（缺少 mode）
        config_data = {
            "agents": {
                "incomplete": {
                    "description": "不完整",
                    # 缺少 mode
                    "allowed_tools": ["read"]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            loaded = registry.load_from_config(config_path)
            
            # 应该跳过不完整的配置
            self.assertEqual(loaded, 0)
            self.assertNotIn("incomplete", registry)
        finally:
            config_path.unlink()


class TestBuiltinAgents(unittest.TestCase):
    """测试内置 agents 的配置"""
    
    def setUp(self):
        AgentRegistry.reset()
        self.registry = AgentRegistry()
    
    def test_build_agent(self):
        """测试 build agent 配置"""
        build = self.registry.get("build")
        
        self.assertEqual(build.name, "build")
        self.assertEqual(build.mode, "primary")
        self.assertIn("*", build.allowed_tools)
        self.assertEqual(build.max_turns, 50)
        self.assertTrue(build.native)
        self.assertFalse(build.hidden)
        self.assertIsNotNone(build.system_prompt)
    
    def test_plan_agent(self):
        """测试 plan agent 配置"""
        plan = self.registry.get("plan")
        
        self.assertEqual(plan.name, "plan")
        self.assertEqual(plan.mode, "primary")
        self.assertIn("read", plan.allowed_tools)
        self.assertIn("grep", plan.allowed_tools)
        self.assertNotIn("write", plan.allowed_tools)
        self.assertEqual(plan.max_turns, 30)
        self.assertTrue(plan.native)
    
    def test_general_agent(self):
        """测试 general agent 配置"""
        general = self.registry.get("general")
        
        self.assertEqual(general.name, "general")
        self.assertEqual(general.mode, "subagent")
        self.assertIn("read", general.allowed_tools)
        self.assertIn("write", general.allowed_tools)
        self.assertNotIn("task", general.allowed_tools)  # 不应包含 task
        self.assertEqual(general.max_turns, 15)
        self.assertTrue(general.native)
    
    def test_explore_agent(self):
        """测试 explore agent 配置"""
        explore = self.registry.get("explore")
        
        self.assertEqual(explore.name, "explore")
        self.assertEqual(explore.mode, "subagent")
        self.assertIn("grep", explore.allowed_tools)
        self.assertIn("glob", explore.allowed_tools)
        self.assertNotIn("write", explore.allowed_tools)
        self.assertEqual(explore.max_turns, 10)
        self.assertTrue(explore.native)
    
    def test_build_can_use_task(self):
        """测试 build agent 可以使用 task 工具"""
        build = self.registry.get("build")
        self.assertTrue(build.can_use_tool("task"))
    
    def test_subagent_cannot_use_task(self):
        """测试 subagent 不能使用 task 工具"""
        general = self.registry.get("general")
        explore = self.registry.get("explore")
        
        # 即使 allowed_tools 包含 "*"，subagent 也不能用 task
        self.assertFalse(general.can_use_tool("task"))
        self.assertFalse(explore.can_use_tool("task"))


if __name__ == '__main__':
    unittest.main()
