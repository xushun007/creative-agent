#!/usr/bin/env python3
"""Todo 工具单元测试"""

import unittest
import asyncio
import json
from unittest.mock import patch

# 添加项目根目录到路径
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from tools.todo import TodoWriteTool, TodoReadTool, TodoState, TodoInfo
    from tools.base_tool import ToolContext
except ImportError:
    # 尝试相对导入
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from tools.todo import TodoWriteTool, TodoReadTool, TodoState, TodoInfo
    from tools.base_tool import ToolContext


class TestTodoTools(unittest.TestCase):
    """Todo 工具测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.write_tool = TodoWriteTool()
        self.read_tool = TodoReadTool()
        self.context = ToolContext(
            session_id="test_session",
            message_id="test_msg",
            agent="test_agent"
        )
        # 清理状态
        TodoState()._todos.clear()
    
    def tearDown(self):
        """测试后清理"""
        TodoState()._todos.clear()
    
    def test_todowrite_basic_functionality(self):
        """测试 TodoWriteTool 基本功能"""
        async def run_test():
            # 创建测试待办事项
            todos_data = [
                {
                    "id": "1",
                    "content": "实现用户登录",
                    "status": "pending",
                    "priority": "high"
                },
                {
                    "id": "2", 
                    "content": "编写测试用例",
                    "status": "in_progress",
                    "priority": "medium"
                }
            ]
            
            # 执行写入
            result = await self.write_tool.execute({"todos": todos_data}, self.context)
            
            # 验证结果
            self.assertEqual(result.title, "2 todos")  # 2个活跃任务
            self.assertIsNotNone(result.output)
            self.assertIn("todos", result.metadata)
            self.assertEqual(len(result.metadata["todos"]), 2)
            
            # 验证输出格式
            output_todos = json.loads(result.output)
            self.assertEqual(len(output_todos), 2)
            self.assertEqual(output_todos[0]["content"], "实现用户登录")
            self.assertEqual(output_todos[1]["status"], "in_progress")
        
        asyncio.run(run_test())
    
    def test_todoread_basic_functionality(self):
        """测试 TodoReadTool 基本功能"""
        async def run_test():
            # 先写入一些待办事项
            todos_data = [
                {
                    "id": "1",
                    "content": "任务1",
                    "status": "completed",
                    "priority": "high"
                },
                {
                    "id": "2",
                    "content": "任务2", 
                    "status": "pending",
                    "priority": "medium"
                }
            ]
            
            await self.write_tool.execute({"todos": todos_data}, self.context)
            
            # 读取待办事项
            result = await self.read_tool.execute({}, self.context)
            
            # 验证结果 - 只有1个活跃任务（completed不计入）
            self.assertEqual(result.title, "1 todos")
            self.assertIsNotNone(result.output)
            self.assertIn("todos", result.metadata)
            
            # 验证读取的数据
            todos = result.metadata["todos"]
            self.assertEqual(len(todos), 2)  # 总共2个任务
            self.assertEqual(todos[0]["content"], "任务1")
            self.assertEqual(todos[1]["status"], "pending")
        
        asyncio.run(run_test())
    
    def test_empty_todo_list(self):
        """测试空待办事项列表"""
        async def run_test():
            # 读取空列表
            result = await self.read_tool.execute({}, self.context)
            
            self.assertEqual(result.title, "0 todos")
            self.assertEqual(result.output, "[]")
            self.assertEqual(result.metadata["todos"], [])
        
        asyncio.run(run_test())
    
    def test_todo_status_counting(self):
        """测试待办事项状态计数"""
        async def run_test():
            # 创建不同状态的待办事项
            todos_data = [
                {"id": "1", "content": "任务1", "status": "pending", "priority": "high"},
                {"id": "2", "content": "任务2", "status": "in_progress", "priority": "medium"},
                {"id": "3", "content": "任务3", "status": "completed", "priority": "low"},
                {"id": "4", "content": "任务4", "status": "cancelled", "priority": "low"},
                {"id": "5", "content": "任务5", "status": "pending", "priority": "medium"}
            ]
            
            result = await self.write_tool.execute({"todos": todos_data}, self.context)
            
            # 应该有4个活跃任务（pending: 2, in_progress: 1, cancelled: 1）
            # 只有 completed 状态不计入活跃任务
            self.assertEqual(result.title, "4 todos")
            
            # 读取验证
            read_result = await self.read_tool.execute({}, self.context)
            self.assertEqual(read_result.title, "4 todos")
        
        asyncio.run(run_test())
    
    def test_session_isolation(self):
        """测试会话隔离"""
        async def run_test():
            # 创建另一个会话上下文
            other_context = ToolContext(
                session_id="other_session",
                message_id="other_msg",
                agent="other_agent"
            )
            
            # 在第一个会话中创建待办事项
            todos1 = [{"id": "1", "content": "会话1任务", "status": "pending", "priority": "high"}]
            await self.write_tool.execute({"todos": todos1}, self.context)
            
            # 在第二个会话中创建待办事项
            todos2 = [{"id": "2", "content": "会话2任务", "status": "pending", "priority": "medium"}]
            await self.write_tool.execute({"todos": todos2}, other_context)
            
            # 验证会话隔离
            result1 = await self.read_tool.execute({}, self.context)
            result2 = await self.read_tool.execute({}, other_context)
            
            self.assertEqual(len(result1.metadata["todos"]), 1)
            self.assertEqual(len(result2.metadata["todos"]), 1)
            self.assertEqual(result1.metadata["todos"][0]["content"], "会话1任务")
            self.assertEqual(result2.metadata["todos"][0]["content"], "会话2任务")
        
        asyncio.run(run_test())
    
    def test_todo_update(self):
        """测试待办事项更新"""
        async def run_test():
            # 创建初始待办事项
            initial_todos = [
                {"id": "1", "content": "任务1", "status": "pending", "priority": "high"},
                {"id": "2", "content": "任务2", "status": "pending", "priority": "medium"}
            ]
            await self.write_tool.execute({"todos": initial_todos}, self.context)
            
            # 更新待办事项状态
            updated_todos = [
                {"id": "1", "content": "任务1", "status": "completed", "priority": "high"},
                {"id": "2", "content": "任务2", "status": "in_progress", "priority": "medium"}
            ]
            result = await self.write_tool.execute({"todos": updated_todos}, self.context)
            
            # 验证更新后只有1个活跃任务
            self.assertEqual(result.title, "1 todos")
            
            # 验证读取结果一致
            read_result = await self.read_tool.execute({}, self.context)
            self.assertEqual(read_result.title, "1 todos")
            
            todos = read_result.metadata["todos"]
            self.assertEqual(todos[0]["status"], "completed")
            self.assertEqual(todos[1]["status"], "in_progress")
        
        asyncio.run(run_test())
    
    def test_tool_parameters_schema(self):
        """测试工具参数模式"""
        # 测试 TodoWriteTool 参数模式
        write_schema = self.write_tool.get_parameters_schema()
        self.assertEqual(write_schema["type"], "object")
        self.assertIn("todos", write_schema["properties"])
        self.assertIn("todos", write_schema["required"])
        
        # 测试 TodoReadTool 参数模式
        read_schema = self.read_tool.get_parameters_schema()
        self.assertEqual(read_schema["type"], "object")
        self.assertEqual(len(read_schema["properties"]), 0)
        self.assertEqual(len(read_schema["required"]), 0)
    
    def test_tool_basic_properties(self):
        """测试工具基本属性"""
        # 测试工具名称
        self.assertEqual(self.write_tool.name, "todowrite")
        self.assertEqual(self.read_tool.name, "todoread")
        
        # 测试描述不为空
        self.assertGreater(len(self.write_tool.description), 0)
        self.assertGreater(len(self.read_tool.description), 0)
        
        # 测试描述包含关键信息
        self.assertIn("待办事项", self.write_tool.description)
        self.assertIn("任务列表", self.read_tool.description)
    
    def test_json_output_format(self):
        """测试 JSON 输出格式"""
        async def run_test():
            todos_data = [
                {"id": "1", "content": "测试任务", "status": "pending", "priority": "high"}
            ]
            
            result = await self.write_tool.execute({"todos": todos_data}, self.context)
            
            # 验证输出是有效的 JSON
            try:
                parsed_output = json.loads(result.output)
                self.assertIsInstance(parsed_output, list)
                self.assertEqual(len(parsed_output), 1)
                self.assertEqual(parsed_output[0]["content"], "测试任务")
            except json.JSONDecodeError:
                self.fail("输出不是有效的 JSON 格式")
        
        asyncio.run(run_test())


class TestTodoState(unittest.TestCase):
    """TodoState 单例测试"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        state1 = TodoState()
        state2 = TodoState()
        
        # 验证是同一个实例
        self.assertIs(state1, state2)
        
        # 验证状态共享
        test_todos = [TodoInfo(id="test", content="测试", status="pending")]
        state1.set_todos("test_session", test_todos)
        
        retrieved_todos = state2.get_todos("test_session")
        self.assertEqual(len(retrieved_todos), 1)
        self.assertEqual(retrieved_todos[0].content, "测试")
        
        # 清理
        TodoState()._todos.clear()


if __name__ == "__main__":
    unittest.main()
