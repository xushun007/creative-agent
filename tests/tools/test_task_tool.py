#!/usr/bin/env python3
"""TaskTool 单元测试"""

import unittest
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from tools.task_tool import TaskTool
from tools.task_manager import TaskManager, SubagentConfig
from tools.task_prompts import get_subagent_prompt, PLAN_AGENT_PROMPT, GENERAL_AGENT_PROMPT, EXPLORE_AGENT_PROMPT
from tools.base_tool import ToolContext


class TestTaskPrompts(unittest.TestCase):
    """任务提示词测试"""
    
    def test_get_plan_prompt(self):
        """测试获取 plan 提示词"""
        prompt = get_subagent_prompt("plan")
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)
        self.assertIn("规划", prompt)
    
    def test_get_general_prompt(self):
        """测试获取 general 提示词"""
        prompt = get_subagent_prompt("general")
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)
        self.assertIn("通用", prompt)
    
    def test_get_explore_prompt(self):
        """测试获取 explore 提示词"""
        prompt = get_subagent_prompt("explore")
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)
        self.assertIn("探索", prompt)
    
    def test_get_unknown_prompt(self):
        """测试获取未知类型提示词"""
        with self.assertRaises(ValueError):
            get_subagent_prompt("unknown_type")
    
    def test_prompt_constants(self):
        """测试提示词常量"""
        self.assertIsInstance(PLAN_AGENT_PROMPT, str)
        self.assertIsInstance(GENERAL_AGENT_PROMPT, str)
        self.assertIsInstance(EXPLORE_AGENT_PROMPT, str)


class TestTaskTool(unittest.TestCase):
    """TaskTool 测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.task_tool = TaskTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        
        # 清理任务管理器状态
        self.task_manager = TaskManager()
        self.task_manager.clear_sessions()
    
    def test_tool_basic_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.task_tool.name, "task")
        self.assertGreater(len(self.task_tool.description), 0)
        self.assertIn("子代理", self.task_tool.description)
    
    def test_parameters_schema(self):
        """测试参数模式"""
        schema = self.task_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("description", schema["properties"])
        self.assertIn("task_prompt", schema["properties"])
        self.assertIn("subagent_type", schema["properties"])
        self.assertIn("context_files", schema["properties"])
        
        required = set(schema["required"])
        self.assertEqual(required, {"description", "task_prompt", "subagent_type"})
        
        # 验证子代理类型枚举
        enum_values = schema["properties"]["subagent_type"]["enum"]
        self.assertIn("plan", enum_values)
        self.assertIn("general", enum_values)
        self.assertIn("explore", enum_values)
    
    def test_default_subagents_registered(self):
        """测试默认子代理已注册"""
        from core.agents import AgentRegistry
        registry = AgentRegistry.get_instance()
        
        # 验证三个可用于 task 工具的 agent（通过 mode=subagent 过滤）
        subagents = registry.list_agents(mode="subagent")
        self.assertGreaterEqual(len(subagents), 2)  # 至少有 general 和 explore
        
        # 验证 general agent（子代理）
        general_agent = registry.get("general")
        self.assertIsNotNone(general_agent)
        self.assertEqual(general_agent.name, "general")
        self.assertEqual(general_agent.mode, "subagent")
        self.assertIn("read", general_agent.allowed_tools)
        self.assertIn("write", general_agent.allowed_tools)
        
        # 验证 explore agent（子代理）
        explore_agent = registry.get("explore")
        self.assertIsNotNone(explore_agent)
        self.assertEqual(explore_agent.name, "explore")
        self.assertEqual(explore_agent.mode, "subagent")
        self.assertIn("read", explore_agent.allowed_tools)
        
        # 验证 plan agent（主代理，不是子代理）
        plan_agent = registry.get("plan")
        self.assertIsNotNone(plan_agent)
        self.assertEqual(plan_agent.name, "plan")
        self.assertEqual(plan_agent.mode, "primary")  # plan 是主代理
        self.assertIn("read", plan_agent.allowed_tools)
    
    def test_plan_agent_configuration(self):
        """测试 plan 代理配置"""
        from core.agents import AgentRegistry
        registry = AgentRegistry.get_instance()
        plan = registry.get("plan")
        
        self.assertEqual(plan.name, "plan")
        self.assertIn("规划", plan.description)
        self.assertEqual(plan.max_turns, 30)  # 实际值为 30
        self.assertEqual(plan.mode, "primary")  # plan 是主代理
        # Plan agent 是只读的
        self.assertIn("read", plan.allowed_tools)
        self.assertIn("grep", plan.allowed_tools)
        self.assertNotIn("write", plan.allowed_tools)
        self.assertNotIn("bash", plan.allowed_tools)
    
    def test_general_agent_configuration(self):
        """测试 general 代理配置"""
        from core.agents import AgentRegistry
        registry = AgentRegistry.get_instance()
        general = registry.get("general")
        
        self.assertEqual(general.name, "general")
        self.assertIn("通用", general.description)
        self.assertEqual(general.max_turns, 30)  # 实际值为 30
        self.assertEqual(general.mode, "subagent")
        # General agent 拥有读写执行权限
        self.assertIn("read", general.allowed_tools)
        self.assertIn("write", general.allowed_tools)
        self.assertIn("bash", general.allowed_tools)
    
    def test_explore_agent_configuration(self):
        """测试 explore 代理配置"""
        from core.agents import AgentRegistry
        registry = AgentRegistry.get_instance()
        explore = registry.get("explore")
        
        self.assertEqual(explore.name, "explore")
        self.assertIn("探索", explore.description)
        self.assertEqual(explore.max_turns, 30)  # 实际值为 30
        self.assertEqual(explore.mode, "subagent")
        # Explore agent 是只读的
        self.assertIn("read", explore.allowed_tools)
        self.assertIn("grep", explore.allowed_tools)
        self.assertNotIn("write", explore.allowed_tools)
        self.assertNotIn("bash", explore.allowed_tools)
    
    def test_unknown_subagent_type_error(self):
        """测试未知子代理类型错误"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "测试任务",
                "task_prompt": "执行某个任务",
                "subagent_type": "nonexistent_agent"
            }, self.context)
            
            self.assertIn("错误", result.title)
            self.assertEqual(result.metadata["error"], "unknown_subagent_type")
            self.assertEqual(result.metadata["requested_type"], "nonexistent_agent")
            self.assertIn("available_types", result.metadata)
        
        asyncio.run(run_test())
    
    def test_plan_agent_execution(self):
        """测试 plan 代理执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "规划缓存模块",
                "task_prompt": "请为项目设计一个缓存模块的技术方案",
                "subagent_type": "plan"
            }, self.context)
            
            self.assertIn("完成", result.title)
            self.assertIn("规划", result.output)
            self.assertEqual(result.metadata["subagent_type"], "plan")
            self.assertEqual(result.metadata["status"], "completed")
            
            # 验证会话已创建
            session_id = result.metadata["session_id"]
            session = self.task_manager.get_session(session_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.status, "completed")
            self.assertEqual(session.subagent_type, "plan")
        
        asyncio.run(run_test())
    
    def test_general_agent_execution(self):
        """测试 general 代理执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "实现功能",
                "task_prompt": "请实现一个简单的配置读取功能",
                "subagent_type": "general"
            }, self.context)
            
            self.assertIn("完成", result.title)
            self.assertEqual(result.metadata["subagent_type"], "general")
            self.assertEqual(result.metadata["status"], "completed")
            
            # 验证会话
            session_id = result.metadata["session_id"]
            session = self.task_manager.get_session(session_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.subagent_type, "general")
        
        asyncio.run(run_test())
    
    def test_explore_agent_execution(self):
        """测试 explore 代理执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "探索代码",
                "task_prompt": "搜索项目中所有的配置文件",
                "subagent_type": "explore"
            }, self.context)
            
            self.assertIn("完成", result.title)
            self.assertIn("探索", result.output)
            self.assertEqual(result.metadata["subagent_type"], "explore")
            self.assertEqual(result.metadata["status"], "completed")
            
            # 验证会话
            session_id = result.metadata["session_id"]
            session = self.task_manager.get_session(session_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.subagent_type, "explore")
        
        asyncio.run(run_test())
    
    def test_task_with_context_files(self):
        """测试带上下文文件的任务"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "分析代码",
                "task_prompt": "分析这些文件的依赖关系",
                "subagent_type": "plan",
                "context_files": ["src/core/session.py", "src/core/config.py"]
            }, self.context)
            
            # 应该成功执行
            self.assertEqual(result.metadata["status"], "completed")
        
        asyncio.run(run_test())
    
    def test_session_tracking(self):
        """测试会话跟踪"""
        async def run_test():
            # 执行任务
            result = await self.task_tool.execute({
                "description": "测试跟踪",
                "task_prompt": "测试会话跟踪功能",
                "subagent_type": "plan"
            }, self.context)
            
            session_id = result.metadata["session_id"]
            
            # 验证会话记录
            session = self.task_manager.get_session(session_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.parent_session_id, self.context.session_id)
            self.assertEqual(session.task_description, "测试跟踪")
            self.assertEqual(session.subagent_type, "plan")
            self.assertEqual(session.status, "completed")
            self.assertIsNotNone(session.result)
            self.assertIsNotNone(session.created_at)
            self.assertIsNotNone(session.completed_at)
        
        asyncio.run(run_test())
    
    def test_multiple_subagent_executions(self):
        """测试多次子代理执行"""
        async def run_test():
            # 执行多个子代理任务
            tasks = []
            for i in range(3):
                task = self.task_tool.execute({
                    "description": f"任务{i}",
                    "task_prompt": f"执行任务{i}",
                    "subagent_type": "explore"
                }, self.context)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            # 验证所有任务都成功
            self.assertEqual(len(results), 3)
            for i, result in enumerate(results):
                self.assertEqual(result.metadata["status"], "completed")
                
                # 每个任务有独立的会话
                session_id = result.metadata["session_id"]
                session = self.task_manager.get_session(session_id)
                self.assertIsNotNone(session)
        
        asyncio.run(run_test())
    
    def test_tool_to_dict(self):
        """测试工具转换为字典"""
        tool_dict = self.task_tool.to_dict()
        
        self.assertEqual(tool_dict["name"], "task")
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        
        params = tool_dict["parameters"]
        self.assertIn("description", params["properties"])
        self.assertIn("task_prompt", params["properties"])
        self.assertIn("subagent_type", params["properties"])
        self.assertIn("context_files", params["properties"])
    
    def test_different_subagent_types(self):
        """测试不同子代理类型返回不同结果"""
        async def run_test():
            # Plan agent
            plan_result = await self.task_tool.execute({
                "description": "规划",
                "task_prompt": "设计方案",
                "subagent_type": "plan"
            }, self.context)
            
            # General agent
            general_result = await self.task_tool.execute({
                "description": "实现",
                "task_prompt": "实现功能",
                "subagent_type": "general"
            }, self.context)
            
            # Explore agent
            explore_result = await self.task_tool.execute({
                "description": "探索",
                "task_prompt": "搜索代码",
                "subagent_type": "explore"
            }, self.context)
            
            # 不同类型的输出应该不同
            self.assertNotEqual(plan_result.output, general_result.output)
            self.assertNotEqual(general_result.output, explore_result.output)
            
            # Plan 输出应该包含规划相关内容
            self.assertIn("技术方案", plan_result.output)
            
            # Explore 输出应该包含探索相关内容
            self.assertIn("代码探索", explore_result.output)
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
