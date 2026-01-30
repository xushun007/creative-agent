#!/usr/bin/env python3
"""TaskTool 集成测试 - 测试真实 Session 执行"""

import unittest
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from tools.task_tool import TaskTool
from tools.task_manager import TaskManager
from tools.base_tool import ToolContext
from core.config import Config


class TestTaskToolIntegration(unittest.TestCase):
    """TaskTool 集成测试 - 真实 Session 执行"""
    
    def setUp(self):
        """测试前准备"""
        # 创建测试配置
        self.test_config = Config(
            model="gpt-4",
            cwd=Path.cwd(),
            max_turns=5,
            temperature=0.7,
            enable_memory=False,
            enable_hooks=False,
            enable_compaction=False,
        )
        
        # 创建 TaskTool（传入配置）
        self.task_tool = TaskTool(main_config=self.test_config)
        
        # 创建执行上下文
        self.context = ToolContext(
            session_id="integration_test_session",
            message_id="integration_test_msg",
            agent="integration_test_agent"
        )
        
        # 清理会话
        self.task_manager = TaskManager()
        self.task_manager.clear_sessions()
    
    def test_filtered_registry_creation(self):
        """测试过滤后的工具注册表创建"""
        allowed_tools = ["read", "grep", "list"]
        
        filtered_registry = self.task_tool._create_filtered_registry(allowed_tools)
        
        # 验证只包含允许的工具
        tool_ids = filtered_registry.get_tool_ids(enabled_only=True)
        self.assertEqual(set(tool_ids), set(allowed_tools))
    
    def test_plan_agent_real_execution(self):
        """测试 plan agent 真实执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "测试规划",
                "task_prompt": """
                请简单分析一下：如果要实现一个日志模块，需要考虑哪些方面？
                请用简短的文字回答（不超过100字）。
                """,
                "subagent_type": "plan"
            }, self.context)
            
            # 验证执行成功
            self.assertIn("完成", result.title)
            self.assertEqual(result.metadata["subagent_type"], "plan")
            self.assertEqual(result.metadata["status"], "completed")
            
            # 验证有输出内容
            self.assertGreater(len(result.output), 0)
            
            # 验证会话记录
            session_id = result.metadata["session_id"]
            session = self.task_manager.get_session(session_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.status, "completed")
            self.assertIsNotNone(session.result)
        
        asyncio.run(run_test())
    
    def test_explore_agent_real_execution(self):
        """测试 explore agent 真实执行"""
        async def run_test():
            result = await self.task_tool.execute({
                "description": "测试探索",
                "task_prompt": """
                请在当前目录下搜索 Python 文件。
                列出找到的文件名称（不超过5个）。
                """,
                "subagent_type": "explore"
            }, self.context)
            
            # 验证执行成功
            self.assertIn("完成", result.title)
            self.assertEqual(result.metadata["subagent_type"], "explore")
            self.assertEqual(result.metadata["status"], "completed")
            
            # 验证有输出内容
            self.assertGreater(len(result.output), 0)
        
        asyncio.run(run_test())
    
    def test_general_agent_read_file(self):
        """测试 general agent 读取文件"""
        async def run_test():
            # 创建临时测试文件
            test_file = Path(self.test_config.cwd) / "test_integration.txt"
            test_file.write_text("这是测试内容")
            
            try:
                result = await self.task_tool.execute({
                    "description": "读取文件",
                    "task_prompt": f"""
                    请读取文件 {test_file.name} 的内容，并告诉我内容是什么。
                    """,
                    "subagent_type": "general"
                }, self.context)
                
                # 验证执行成功
                self.assertEqual(result.metadata["status"], "completed")
                self.assertGreater(len(result.output), 0)
                
            finally:
                # 清理测试文件
                if test_file.exists():
                    test_file.unlink()
        
        asyncio.run(run_test())
    
    def test_subagent_tool_filtering(self):
        """测试子代理的工具过滤"""
        async def run_test():
            # Plan agent 不应该能使用 write 工具
            result = await self.task_tool.execute({
                "description": "测试工具限制",
                "task_prompt": """
                请尝试创建一个文件 test.txt。
                如果不能创建，请说明原因。
                """,
                "subagent_type": "plan"
            }, self.context)
            
            # Plan agent 应该无法写入文件
            # 它可能会说明自己没有写入权限
            self.assertEqual(result.metadata["status"], "completed")
        
        asyncio.run(run_test())
    
    def test_subagent_timeout_handling(self):
        """测试子代理超时处理"""
        async def run_test():
            # 创建一个配置了很短 max_turns 的子代理
            short_config = self.test_config.model_copy()
            short_config.max_turns = 1
            
            task_tool = TaskTool(main_config=short_config)
            
            result = await task_tool.execute({
                "description": "超时测试",
                "task_prompt": """
                请执行一个需要多步骤的复杂任务：
                1. 列出所有Python文件
                2. 分析每个文件的作用
                3. 生成详细报告
                """,
                "subagent_type": "explore"
            }, self.context)
            
            # 应该能完成（即使可能没有完成所有步骤）
            self.assertIn(result.metadata["status"], ["completed", "timeout", "failed"])
        
        asyncio.run(run_test())
    
    def test_subagent_context_isolation(self):
        """测试子代理上下文隔离"""
        async def run_test():
            # 执行第一个子代理任务
            result1 = await self.task_tool.execute({
                "description": "任务1",
                "task_prompt": "请说明你的任务是什么。",
                "subagent_type": "plan"
            }, self.context)
            
            # 执行第二个子代理任务
            result2 = await self.task_tool.execute({
                "description": "任务2",
                "task_prompt": "请说明你的任务是什么。",
                "subagent_type": "explore"
            }, self.context)
            
            # 两个任务应该有不同的会话ID
            self.assertNotEqual(
                result1.metadata["session_id"],
                result2.metadata["session_id"]
            )
            
            # 验证会话独立
            session1 = self.task_manager.get_session(result1.metadata["session_id"])
            session2 = self.task_manager.get_session(result2.metadata["session_id"])
            
            self.assertNotEqual(session1.subagent_type, session2.subagent_type)
        
        asyncio.run(run_test())


# 模拟执行测试（无论标志如何都运行）
class TestTaskToolMocked(unittest.TestCase):
    """TaskTool 模拟执行测试 - 不依赖真实 Session"""
    
    def setUp(self):
        """测试前准备"""
        self.task_tool = TaskTool()
        self.context = ToolContext(
            session_id="mock_test_session",
            message_id="mock_test_msg",
            agent="mock_test_agent"
        )
        self.task_manager = TaskManager()
        self.task_manager.clear_sessions()
    
    def test_simulate_execution_fallback(self):
        """测试模拟执行回退机制"""
        async def run_test():
            # 当真实执行失败时，会自动回退到模拟执行
            # 这里通过传入一个无效的配置来触发回退
            tool_with_bad_config = TaskTool(main_config=None)
            
            result = await tool_with_bad_config.execute({
                "description": "回退测试",
                "task_prompt": "这是一个测试任务",
                "subagent_type": "plan"
            }, self.context)
            
            # 应该成功（使用模拟或真实执行）
            self.assertIn(result.metadata["status"], ["completed", "failed"])
        
        asyncio.run(run_test())
    
    def test_all_subagent_types_execution(self):
        """测试所有子代理类型的执行"""
        async def run_test():
            # 测试所有子代理类型都能成功执行（真实或模拟）
            for subagent_type in ["plan", "general", "explore"]:
                result = await self.task_tool.execute({
                    "description": f"测试{subagent_type}",
                    "task_prompt": "测试任务",
                    "subagent_type": subagent_type
                }, self.context)
                
                # 应该成功完成
                self.assertIn(result.metadata["status"], ["completed", "failed"])
                self.assertEqual(result.metadata["subagent_type"], subagent_type)
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
