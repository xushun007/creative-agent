#!/usr/bin/env python3
"""TaskTool 单元测试"""

import unittest
import asyncio

# 添加项目根目录到路径
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.task_tool import TaskTool, TaskManager, AgentConfig, TaskSession
    from tools.base_tool import ToolContext
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.task_tool import TaskTool, TaskManager, AgentConfig, TaskSession
    from tools.base_tool import ToolContext


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
        self.task_manager._sessions.clear()
    
    def test_tool_basic_properties(self):
        """测试工具基本属性"""
        self.assertEqual(self.task_tool.name, "task")
        self.assertGreater(len(self.task_tool.description), 0)
        self.assertIn("代理", self.task_tool.description)
        self.assertIn("多步骤任务", self.task_tool.description)
    
    def test_parameters_schema(self):
        """测试参数模式"""
        schema = self.task_tool.get_parameters_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("description", schema["properties"])
        self.assertIn("prompt", schema["properties"])
        self.assertIn("subagent_type", schema["properties"])
        
        required = set(schema["required"])
        self.assertEqual(required, {"description", "prompt", "subagent_type"})
        
        # 验证代理类型枚举
        enum_values = schema["properties"]["subagent_type"]["enum"]
        self.assertIn("code_reviewer", enum_values)
        self.assertIn("file_searcher", enum_values)
        self.assertIn("test_generator", enum_values)
    
    def test_task_manager_singleton(self):
        """测试 TaskManager 单例模式"""
        manager1 = TaskManager()
        manager2 = TaskManager()
        
        self.assertIs(manager1, manager2)
    
    def test_agent_registration(self):
        """测试代理注册"""
        manager = TaskManager()
        
        # 注册新代理
        test_agent = AgentConfig(
            name="test_agent",
            description="测试代理",
            tools={"read": True}
        )
        
        initial_count = len(manager.get_agents())
        manager.register_agent(test_agent)
        
        self.assertEqual(len(manager.get_agents()), initial_count + 1)
        
        # 验证代理可以获取
        retrieved_agent = manager.get_agent("test_agent")
        self.assertIsNotNone(retrieved_agent)
        self.assertEqual(retrieved_agent.name, "test_agent")
        self.assertEqual(retrieved_agent.description, "测试代理")
        
        # 重复注册应该不增加数量
        manager.register_agent(test_agent)
        self.assertEqual(len(manager.get_agents()), initial_count + 1)
    
    def test_session_creation_and_management(self):
        """测试会话创建和管理"""
        manager = TaskManager()
        
        # 创建会话
        session = manager.create_session(
            parent_session_id="parent_123",
            description="测试任务",
            agent_name="code_reviewer"
        )
        
        self.assertIsNotNone(session.id)
        self.assertEqual(session.description, "测试任务")
        self.assertEqual(session.agent, "code_reviewer")
        self.assertEqual(session.status, "running")
        
        # 获取会话
        retrieved_session = manager.get_session(session.id)
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session.id, session.id)
        
        # 中止会话
        manager.abort_session(session.id)
        self.assertEqual(retrieved_session.status, "aborted")
    
    def test_code_reviewer_task_execution(self):
        """测试代码审查代理任务执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "审查代码",
                "prompt": "请审查以下Python代码的质量和安全性：\ndef process_data(data): return data.upper()",
                "subagent_type": "code_reviewer"
            }, self.context)
            
            self.assertEqual(result.title, "审查代码")
            self.assertIn("代码审查完成", result.output)
            self.assertIn("错误处理", result.output)
            
            # 验证元数据
            self.assertIn("session_id", result.metadata)
            self.assertEqual(result.metadata["agent"], "code_reviewer")
            self.assertEqual(result.metadata["status"], "completed")
            self.assertIn("summary", result.metadata)
        
        asyncio.run(run_test())
    
    def test_file_searcher_task_execution(self):
        """测试文件搜索代理任务执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "搜索文件",
                "prompt": "在项目中搜索所有包含'import pandas'的Python文件",
                "subagent_type": "file_searcher"
            }, self.context)
            
            self.assertEqual(result.title, "搜索文件")
            self.assertIn("文件搜索完成", result.output)
            self.assertIn("相关文件", result.output)
            
            self.assertEqual(result.metadata["agent"], "file_searcher")
            self.assertEqual(result.metadata["status"], "completed")
        
        asyncio.run(run_test())
    
    def test_test_generator_task_execution(self):
        """测试测试生成代理任务执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "生成测试",
                "prompt": "为Calculator类生成完整的单元测试",
                "subagent_type": "test_generator"
            }, self.context)
            
            self.assertEqual(result.title, "生成测试")
            self.assertIn("测试生成完成", result.output)
            self.assertIn("单元测试", result.output)
            self.assertIn("集成测试", result.output)
            
            self.assertEqual(result.metadata["agent"], "test_generator")
        
        asyncio.run(run_test())
    
    def test_doc_generator_task_execution(self):
        """测试文档生成代理任务执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "生成文档",
                "prompt": "为API模块生成详细的文档",
                "subagent_type": "doc_generator"
            }, self.context)
            
            self.assertEqual(result.title, "生成文档")
            self.assertIn("文档生成完成", result.output)
            self.assertIn("API 文档", result.output)
            
            self.assertEqual(result.metadata["agent"], "doc_generator")
        
        asyncio.run(run_test())
    
    def test_refactor_agent_task_execution(self):
        """测试重构代理任务执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "重构代码",
                "prompt": "重构legacy_module.py中的代码，提高可读性和性能",
                "subagent_type": "refactor_agent"
            }, self.context)
            
            self.assertEqual(result.title, "重构代码")
            self.assertIn("重构完成", result.output)
            self.assertIn("提取公共方法", result.output)
            self.assertIn("性能提升", result.output)
            
            self.assertEqual(result.metadata["agent"], "refactor_agent")
        
        asyncio.run(run_test())
    
    def test_unknown_agent_type_error(self):
        """测试未知代理类型错误"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "测试任务",
                "prompt": "执行某个任务",
                "subagent_type": "nonexistent_agent"
            }, self.context)
            
            self.assertIn("错误", result.title)
            self.assertEqual(result.metadata["error"], "unknown_agent_type")
            self.assertEqual(result.metadata["requested_type"], "nonexistent_agent")
            self.assertIn("available_types", result.metadata)
        
        asyncio.run(run_test())
    
    def test_agent_configuration(self):
        """测试代理配置"""
        manager = TaskManager()
        agents = manager.get_agents()
        
        # 验证默认代理配置
        agent_names = [agent.name for agent in agents]
        expected_agents = [
            "code_reviewer", "file_searcher", "test_generator", 
            "doc_generator", "refactor_agent"
        ]
        
        for expected in expected_agents:
            self.assertIn(expected, agent_names)
        
        # 验证代理工具配置
        code_reviewer = manager.get_agent("code_reviewer")
        self.assertIsNotNone(code_reviewer)
        self.assertTrue(code_reviewer.tools.get("read", False))
        self.assertTrue(code_reviewer.tools.get("grep", False))
        self.assertFalse(code_reviewer.tools.get("bash", True))
        
        test_generator = manager.get_agent("test_generator")
        self.assertIsNotNone(test_generator)
        self.assertTrue(test_generator.tools.get("write", False))
        self.assertTrue(test_generator.tools.get("bash", False))
    
    def test_session_tracking(self):
        """测试会话跟踪"""
        async def run_test():
            # 执行任务并验证会话创建
            result = await self.task_tool.execute({
                "description": "跟踪测试",
                "prompt": "测试会话跟踪功能",
                "subagent_type": "code_reviewer"
            }, self.context)
            
            session_id = result.metadata["session_id"]
            self.assertIsNotNone(session_id)
            
            # 验证会话存在
            session = self.task_manager.get_session(session_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.description, "跟踪测试")
            self.assertEqual(session.agent, "code_reviewer")
            self.assertEqual(session.status, "completed")
            
            # 验证消息记录
            self.assertGreater(len(session.messages), 0)
            last_message = session.messages[-1]
            self.assertEqual(last_message["role"], "assistant")
            self.assertIn("content", last_message)
        
        asyncio.run(run_test())
    
    def test_concurrent_task_execution(self):
        """测试并发任务执行"""
        async def run_test():
            # 创建多个并发任务
            tasks = [
                self.task_tool.execute({
                    "description": f"任务{i}",
                    "prompt": f"执行任务{i}",
                    "subagent_type": "code_reviewer"
                }, self.context)
                for i in range(3)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # 验证所有任务都成功完成
            self.assertEqual(len(results), 3)
            for i, result in enumerate(results):
                self.assertEqual(result.title, f"任务{i}")
                self.assertEqual(result.metadata["status"], "completed")
                self.assertIn("session_id", result.metadata)
            
            # 验证每个任务都有独立的会话
            session_ids = [result.metadata["session_id"] for result in results]
            self.assertEqual(len(set(session_ids)), 3)  # 所有会话ID应该不同
        
        asyncio.run(run_test())
    
    def test_tool_to_dict(self):
        """测试工具转换为字典"""
        tool_dict = self.task_tool.to_dict()
        
        self.assertEqual(tool_dict["name"], "task")
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        
        params = tool_dict["parameters"]
        self.assertIn("description", params["properties"])
        self.assertIn("prompt", params["properties"])
        self.assertIn("subagent_type", params["properties"])
        
        # 验证代理类型枚举
        enum_values = params["properties"]["subagent_type"]["enum"]
        self.assertIsInstance(enum_values, list)
        self.assertGreater(len(enum_values), 0)


class TestAgentConfig(unittest.TestCase):
    """AgentConfig 测试类"""
    
    def test_agent_config_creation(self):
        """测试代理配置创建"""
        agent = AgentConfig(
            name="test_agent",
            description="测试代理",
            mode="secondary",
            tools={"read": True, "write": False},
            model_id="gpt-4",
            provider_id="openai"
        )
        
        self.assertEqual(agent.name, "test_agent")
        self.assertEqual(agent.description, "测试代理")
        self.assertEqual(agent.mode, "secondary")
        self.assertTrue(agent.tools["read"])
        self.assertFalse(agent.tools["write"])
        self.assertEqual(agent.model_id, "gpt-4")
        self.assertEqual(agent.provider_id, "openai")
    
    def test_agent_config_defaults(self):
        """测试代理配置默认值"""
        agent = AgentConfig(
            name="minimal_agent",
            description="最小代理"
        )
        
        self.assertEqual(agent.mode, "secondary")
        self.assertEqual(agent.tools, {})
        self.assertIsNone(agent.model_id)
        self.assertIsNone(agent.provider_id)


class TestTaskSession(unittest.TestCase):
    """TaskSession 测试类"""
    
    def test_task_session_creation(self):
        """测试任务会话创建"""
        session = TaskSession(
            id="session_123",
            description="测试会话",
            agent="test_agent"
        )
        
        self.assertEqual(session.id, "session_123")
        self.assertEqual(session.description, "测试会话")
        self.assertEqual(session.agent, "test_agent")
        self.assertEqual(session.status, "running")
        self.assertEqual(session.messages, [])
        self.assertEqual(session.metadata, {})
    
    def test_task_session_message_handling(self):
        """测试任务会话消息处理"""
        session = TaskSession(
            id="session_456",
            description="消息测试",
            agent="test_agent"
        )
        
        # 添加消息
        message = {
            "role": "assistant",
            "content": "任务完成",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        session.messages.append(message)
        
        self.assertEqual(len(session.messages), 1)
        self.assertEqual(session.messages[0]["content"], "任务完成")


if __name__ == "__main__":
    unittest.main()
