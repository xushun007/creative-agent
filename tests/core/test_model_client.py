#!/usr/bin/env python3
"""ModelClient 单元测试"""

import unittest
import asyncio
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from core.model_client import ModelClient, Message, ChatResponse
    from core.config import Config
    from core.protocol import TokenUsage
    from tools.registry import ToolRegistry, get_global_registry, reset_global_registry
    from tools.base_tool import BaseTool, ToolContext, ToolResult
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


class TestMessage(unittest.TestCase):
    """测试 Message 数据类"""
    
    def test_message_creation_basic(self):
        """测试基本消息创建"""
        msg = Message("user", "Hello, world!")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello, world!")
        self.assertIsNone(msg.tool_calls)
        self.assertIsNone(msg.tool_call_id)
    
    def test_message_creation_with_tool_calls(self):
        """测试带工具调用的消息创建"""
        tool_calls = [{"id": "call_123", "type": "function", "function": {"name": "test", "arguments": "{}"}}]
        msg = Message("assistant", "I'll help you", tool_calls=tool_calls)
        self.assertEqual(msg.role, "assistant")
        self.assertEqual(msg.content, "I'll help you")
        self.assertEqual(msg.tool_calls, tool_calls)
        self.assertIsNone(msg.tool_call_id)
    
    def test_message_creation_tool_response(self):
        """测试工具响应消息创建"""
        msg = Message("tool", "Tool result", tool_call_id="call_123")
        self.assertEqual(msg.role, "tool")
        self.assertEqual(msg.content, "Tool result")
        self.assertIsNone(msg.tool_calls)
        self.assertEqual(msg.tool_call_id, "call_123")


class TestChatResponse(unittest.TestCase):
    """测试 ChatResponse 数据类"""
    
    def test_chat_response_creation(self):
        """测试聊天响应创建"""
        token_usage = TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        tool_calls = [{"id": "call_123", "type": "function"}]
        
        response = ChatResponse(
            content="Hello!",
            tool_calls=tool_calls,
            token_usage=token_usage,
            finish_reason="stop",
            reasoning_content="思考过程"
        )
        
        self.assertEqual(response.content, "Hello!")
        self.assertEqual(response.tool_calls, tool_calls)
        self.assertEqual(response.token_usage, token_usage)
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.reasoning_content, "思考过程")
    
    def test_chat_response_minimal(self):
        """测试最小聊天响应"""
        token_usage = TokenUsage()
        response = ChatResponse("Hi", [], token_usage, "stop")
        
        self.assertEqual(response.content, "Hi")
        self.assertEqual(response.tool_calls, [])
        self.assertEqual(response.token_usage, token_usage)
        self.assertEqual(response.finish_reason, "stop")
        self.assertIsNone(response.reasoning_content)


# 测试用的模拟工具
class MockTool(BaseTool[Dict[str, Any]]):
    """测试用模拟工具"""
    
    def __init__(self):
        super().__init__("mock_tool", "A mock tool for testing")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Test text"}
            },
            "required": ["text"]
        }
    
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(success=True, result=f"Mock result: {params.get('text', '')}")


class TestModelClient(unittest.TestCase):
    """测试 ModelClient 类"""
    
    def setUp(self):
        """测试前置设置"""
        # 创建临时配置
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(
            model="gpt-3.5-turbo",
            api_key="test-key",
            api_base="https://api.openai.com/v1",
            cwd=Path(self.temp_dir),
            max_tokens=1000,
            temperature=0.7
        )
        
        # 重置工具注册表
        reset_global_registry()
        self.registry = get_global_registry()
        
        # 注册测试工具类
        self.registry.register_tool(MockTool)
    
    def tearDown(self):
        """测试清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_global_registry()
    
    def test_model_client_initialization(self):
        """测试 ModelClient 初始化"""
        client = ModelClient(self.config, self.registry)
        
        self.assertEqual(client.config, self.config)
        self.assertEqual(client.tool_registry, self.registry)
        self.assertIsNotNone(client.client)
        self.assertIsInstance(client.conversation_history, list)
        
        # 检查是否添加了系统消息
        self.assertGreater(len(client.conversation_history), 0)
        self.assertEqual(client.conversation_history[0].role, "system")
    
    def test_add_system_message(self):
        """测试添加系统消息"""
        client = ModelClient(self.config)
        initial_count = len(client.conversation_history)
        
        client.add_system_message("新系统消息")
        
        self.assertEqual(len(client.conversation_history), initial_count + 1)
        last_msg = client.conversation_history[-1]
        self.assertEqual(last_msg.role, "system")
        self.assertEqual(last_msg.content, "新系统消息")
    
    def test_add_user_message(self):
        """测试添加用户消息"""
        client = ModelClient(self.config)
        initial_count = len(client.conversation_history)
        
        client.add_user_message("用户问题")
        
        self.assertEqual(len(client.conversation_history), initial_count + 1)
        last_msg = client.conversation_history[-1]
        self.assertEqual(last_msg.role, "user")
        self.assertEqual(last_msg.content, "用户问题")
    
    def test_add_assistant_message(self):
        """测试添加助手消息"""
        client = ModelClient(self.config)
        initial_count = len(client.conversation_history)
        
        tool_calls = [{"id": "call_123", "type": "function"}]
        client.add_assistant_message("助手回复", tool_calls)
        
        self.assertEqual(len(client.conversation_history), initial_count + 1)
        last_msg = client.conversation_history[-1]
        self.assertEqual(last_msg.role, "assistant")
        self.assertEqual(last_msg.content, "助手回复")
        self.assertEqual(last_msg.tool_calls, tool_calls)
    
    def test_add_tool_message(self):
        """测试添加工具消息"""
        client = ModelClient(self.config)
        initial_count = len(client.conversation_history)
        
        client.add_tool_message("call_123", "工具执行结果")
        
        self.assertEqual(len(client.conversation_history), initial_count + 1)
        last_msg = client.conversation_history[-1]
        self.assertEqual(last_msg.role, "tool")
        self.assertEqual(last_msg.content, "工具执行结果")
        self.assertEqual(last_msg.tool_call_id, "call_123")
    
    def test_clear_history(self):
        """测试清空对话历史"""
        client = ModelClient(self.config)
        client.add_user_message("测试消息")
        
        self.assertGreater(len(client.conversation_history), 0)
        
        client.clear_history()
        
        self.assertEqual(len(client.conversation_history), 0)
    
    def test_get_tools_schema(self):
        """测试获取工具模式"""
        client = ModelClient(self.config, self.registry)
        
        tools_schema = client.get_tools_schema()
        
        self.assertIsInstance(tools_schema, list)
        self.assertGreater(len(tools_schema), 0)
        
        # 检查第一个工具的结构
        tool = tools_schema[0]
        self.assertEqual(tool["type"], "function")
        self.assertIn("function", tool)
        self.assertIn("name", tool["function"])
        self.assertIn("description", tool["function"])
        self.assertIn("parameters", tool["function"])
    
    def test_setup_system_messages_with_tool_registry(self):
        """测试带工具注册表的系统消息设置"""
        client = ModelClient(self.config, self.registry)
        
        # 检查系统消息内容
        system_msg = client.conversation_history[0]
        self.assertIn("mock_tool", system_msg.content)
        self.assertIn("当前工作目录", system_msg.content)
        self.assertIn("可用工具", system_msg.content)
    
    def test_setup_system_messages_without_tool_registry(self):
        """测试不带工具注册表的系统消息设置"""
        client = ModelClient(self.config)
        
        # 应该仍有系统消息，但不包含工具信息
        self.assertGreater(len(client.conversation_history), 0)
        system_msg = client.conversation_history[0]
        self.assertEqual(system_msg.role, "system")
    
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="文件中的系统提示词")
    def test_setup_system_messages_from_file(self, mock_open):
        """测试从文件读取系统提示词"""
        client = ModelClient(self.config, self.registry)
        
        system_msg = client.conversation_history[0]
        self.assertIn("文件中的系统提示词", system_msg.content)
    
    def test_setup_system_messages_with_user_instructions(self):
        """测试带用户自定义指令的系统消息设置"""
        config_with_user_instructions = Config(
            model="gpt-3.5-turbo",
            api_key="test-key",
            user_instructions="请用中文回复"
        )
        
        client = ModelClient(config_with_user_instructions)
        
        system_msg = client.conversation_history[0]
        self.assertIn("请用中文回复", system_msg.content)


class TestModelClientAsync(unittest.IsolatedAsyncioTestCase):
    """测试 ModelClient 异步方法"""
    
    def setUp(self):
        """测试前置设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config(
            model="gpt-3.5-turbo",
            api_key="test-key",
            api_base="https://api.openai.com/v1",
            cwd=Path(self.temp_dir)
        )
        
        # 重置工具注册表
        reset_global_registry()
        self.registry = get_global_registry()
        self.registry.register_tool(MockTool)
    
    def tearDown(self):
        """测试清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_global_registry()
    
    async def test_non_stream_completion(self):
        """测试非流式聊天完成"""
        # 模拟 OpenAI 响应
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "测试响应"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        
        client = ModelClient(self.config, self.registry)
        client.add_user_message("测试问题")
        
        # 直接模拟client的chat.completions.create方法
        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock, return_value=mock_response):
            response = await client.chat_completion(stream=False)
        
        self.assertIsInstance(response, ChatResponse)
        self.assertEqual(response.content, "测试响应")
        self.assertEqual(response.tool_calls, [])
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.token_usage.total_tokens, 30)
    
    async def test_non_stream_completion_with_tool_calls(self):
        """测试带工具调用的非流式聊天完成"""
        # 模拟带工具调用的响应
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "mock_tool"
        mock_tool_call.function.arguments = '{"text": "test"}'
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "我将使用工具"
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 40
        
        client = ModelClient(self.config, self.registry)
        client.add_user_message("请使用工具")
        
        # 直接模拟client的chat.completions.create方法
        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock, return_value=mock_response):
            response = await client.chat_completion(stream=False)
        
        self.assertIsInstance(response, ChatResponse)
        self.assertEqual(response.content, "我将使用工具")
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0]["id"], "call_123")
        self.assertEqual(response.tool_calls[0]["function"]["name"], "mock_tool")
        self.assertEqual(response.finish_reason, "tool_calls")
    
    async def test_stream_completion(self):
        """测试流式聊天完成"""
        # 模拟流式响应
        async def mock_stream():
            chunks = [
                Mock(choices=[Mock(delta=Mock(content="你好", tool_calls=None, reasoning_content=None))]),
                Mock(choices=[Mock(delta=Mock(content="，世界", tool_calls=None, reasoning_content=None))]),
                Mock(choices=[Mock(delta=Mock(content="！", tool_calls=None, reasoning_content=None))])
            ]
            for chunk in chunks:
                yield chunk
        
        client = ModelClient(self.config, self.registry)
        client.add_user_message("你好")
        
        # 直接模拟client的chat.completions.create方法
        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock, return_value=mock_stream()):
            response = await client.chat_completion(stream=True)
        
        self.assertIsInstance(response, ChatResponse)
        self.assertEqual(response.content, "你好，世界！")
        self.assertEqual(response.finish_reason, "stop")
        # 流式模式下token使用情况为空
        self.assertEqual(response.token_usage.total_tokens, 0)
    
    async def test_stream_completion_events(self):
        """测试流式完成事件生成器"""
        # 模拟流式响应
        async def mock_stream():
            chunks = [
                Mock(choices=[Mock(delta=Mock(content="测试", tool_calls=None))]),
                Mock(choices=[Mock(delta=Mock(content="内容", tool_calls=None))])
            ]
            for chunk in chunks:
                yield chunk
        
        client = ModelClient(self.config, self.registry)
        
        messages = [{"role": "user", "content": "测试"}]
        content_parts = []
        
        # 直接模拟client的chat.completions.create方法
        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock, return_value=mock_stream()):
            async for content in client.stream_completion_events(messages):
                content_parts.append(content)
        
        self.assertEqual(content_parts, ["测试", "内容"])
    
    async def test_chat_completion_api_error(self):
        """测试API错误处理"""
        client = ModelClient(self.config, self.registry)
        client.add_user_message("测试")
        
        # 直接模拟client的chat.completions.create方法抛出异常
        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock, side_effect=Exception("API错误")):
            with self.assertRaises(Exception) as context:
                await client.chat_completion()
        
        self.assertIn("模型请求失败", str(context.exception))
        self.assertIn("API错误", str(context.exception))


if __name__ == '__main__':
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    unittest.main()
