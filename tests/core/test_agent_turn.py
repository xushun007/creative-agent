#!/usr/bin/env python3
"""AgentTurn 单元测试"""

import unittest
from unittest.mock import AsyncMock, MagicMock

import sys
import os
from pathlib import Path


# 添加项目根目录到 Python 路径，保持与现有测试一致
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from core.agent_turn import AgentTurn, AgentTurnResult  # noqa: E402
from core.model_client import ChatResponse  # noqa: E402
from core.protocol import TokenUsage  # noqa: E402
from tools.base_tool import ToolResult  # noqa: E402


class AgentTurnTestCase(unittest.IsolatedAsyncioTestCase):
    """覆盖 AgentTurn 核心流程的单元测试"""

    def setUp(self):
        self.model_client = MagicMock()
        self.model_client.chat_completion = AsyncMock()
        self.model_client.add_assistant_message = MagicMock()
        self.model_client.add_tool_message = MagicMock()

        self.tool_registry = MagicMock()
        self.tool_registry.execute_tool = AsyncMock()

        # 事件处理器的所有方法都是异步的
        self.event_handler = MagicMock()
        for method_name in [
            'emit_agent_message',
            'emit_tool_start',
            'emit_tool_end',
            'emit_error',
            'emit',  # 添加通用的emit方法
        ]:
            setattr(self.event_handler, method_name, AsyncMock())

        self.agent_turn = AgentTurn(
            model_client=self.model_client,
            tool_registry=self.tool_registry,
            event_handler=self.event_handler,
            session_id='session-test',
        )

    async def test_execute_turn_with_text_only(self):
        """单纯文本响应时应返回内容并发送事件"""

        token_usage = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)
        response = ChatResponse(
            content='Hello, world!',
            tool_calls=[],
            token_usage=token_usage,
            finish_reason='stop',
        )
        self.model_client.chat_completion.return_value = response

        result = await self.agent_turn.execute_turn('submission-1')

        self.model_client.add_assistant_message.assert_called_once_with('Hello, world!', None)
        self.event_handler.emit_agent_message.assert_awaited_once_with('submission-1', 'Hello, world!')

        self.assertIsInstance(result, AgentTurnResult)
        self.assertEqual(result.text_content, 'Hello, world!')
        self.assertEqual(result.token_usage, token_usage)
        self.assertFalse(result.has_tool_calls())

    async def test_execute_turn_with_tool_call(self):
        """当模型返回工具调用时应按顺序执行并记录结果"""

        tool_call = {
            'id': 'call-123',
            'type': 'function',
            'function': {
                'name': 'read',
                'arguments': '{"filePath": "/tmp/demo.txt"}',
            },
        }
        token_usage = TokenUsage(input_tokens=12, output_tokens=8, total_tokens=20)
        response = ChatResponse(
            content='处理文件',
            tool_calls=[tool_call],
            token_usage=token_usage,
            finish_reason='tool_calls',
        )
        self.model_client.chat_completion.return_value = response

        self.tool_registry.execute_tool.return_value = ToolResult(
            title='demo.txt',
            output='文件内容',
        )

        result = await self.agent_turn.execute_turn('submission-2')

        self.tool_registry.execute_tool.assert_awaited_once()
        called_name = self.tool_registry.execute_tool.await_args.args[0]
        self.assertEqual(called_name, 'read')

        self.model_client.add_tool_message.assert_called_once_with('call-123', '文件内容')
        self.event_handler.emit_tool_start.assert_awaited_once()
        self.event_handler.emit_tool_end.assert_awaited_once()

        self.assertTrue(result.has_tool_calls())
        self.assertTrue(result.has_successful_tool_calls())
        self.assertEqual(result.tool_responses[0].result, '文件内容')

    async def test_execute_turn_with_multiple_tool_calls(self):
        """测试多个工具调用的顺序执行"""
        
        tool_call_1 = {
            'id': 'call-123',
            'type': 'function',
            'function': {
                'name': 'read',
                'arguments': '{"filePath": "/tmp/file1.txt"}',
            },
        }
        tool_call_2 = {
            'id': 'call-456',
            'type': 'function',
            'function': {
                'name': 'write',
                'arguments': '{"filePath": "/tmp/file2.txt", "content": "test"}',
            },
        }
        
        token_usage = TokenUsage(input_tokens=15, output_tokens=10, total_tokens=25)
        response = ChatResponse(
            content='处理多个文件',
            tool_calls=[tool_call_1, tool_call_2],
            token_usage=token_usage,
            finish_reason='tool_calls',
        )
        self.model_client.chat_completion.return_value = response

        # 设置工具执行结果
        self.tool_registry.execute_tool.side_effect = [
            ToolResult(title='file1.txt', output='文件1内容'),
            ToolResult(title='file2.txt', output='写入成功'),
        ]

        result = await self.agent_turn.execute_turn('submission-3')

        # 验证工具调用次数
        self.assertEqual(self.tool_registry.execute_tool.await_count, 2)
        
        # 验证工具消息添加
        self.assertEqual(self.model_client.add_tool_message.call_count, 2)
        self.model_client.add_tool_message.assert_any_call('call-123', '文件1内容')
        self.model_client.add_tool_message.assert_any_call('call-456', '写入成功')
        
        # 验证事件发送
        self.assertEqual(self.event_handler.emit_tool_start.await_count, 2)
        self.assertEqual(self.event_handler.emit_tool_end.await_count, 2)
        
        # 验证结果
        self.assertTrue(result.has_tool_calls())
        self.assertTrue(result.has_successful_tool_calls())
        self.assertEqual(len(result.tool_responses), 2)
        self.assertEqual(result.tool_responses[0].result, '文件1内容')
        self.assertEqual(result.tool_responses[1].result, '写入成功')

    async def test_execute_turn_with_llm_exception(self):
        """测试LLM调用异常时的错误处理"""
        
        # 模拟LLM调用异常
        self.model_client.chat_completion.side_effect = Exception("LLM服务不可用")

        result = await self.agent_turn.execute_turn('submission-4')

        # 验证错误事件发送
        self.event_handler.emit_error.assert_awaited_once_with(
            'submission-4', '回合执行失败: LLM服务不可用'
        )
        
        # 验证错误结果
        self.assertIn('执行出错: LLM服务不可用', result.text_content)
        self.assertIsNotNone(result.duration_ms)
        self.assertFalse(result.has_tool_calls())

    async def test_execute_turn_with_tool_execution_failure(self):
        """测试工具执行失败时的处理"""
        
        tool_call = {
            'id': 'call-789',
            'type': 'function',
            'function': {
                'name': 'invalid_tool',
                'arguments': '{"param": "value"}',
            },
        }
        
        token_usage = TokenUsage(input_tokens=8, output_tokens=6, total_tokens=14)
        response = ChatResponse(
            content='尝试调用工具',
            tool_calls=[tool_call],
            token_usage=token_usage,
            finish_reason='tool_calls',
        )
        self.model_client.chat_completion.return_value = response

        # 模拟工具执行异常
        self.tool_registry.execute_tool.side_effect = Exception("工具不存在")

        result = await self.agent_turn.execute_turn('submission-5')

        # 验证工具失败处理
        self.assertTrue(result.has_tool_calls())
        self.assertFalse(result.has_successful_tool_calls())
        self.assertEqual(len(result.tool_responses), 1)
        self.assertFalse(result.tool_responses[0].success)
        self.assertEqual(result.tool_responses[0].error, '工具不存在')
        
        # 验证错误消息添加到对话历史
        self.model_client.add_tool_message.assert_called_once_with(
            'call-789', '工具不存在'
        )
        
        # 验证错误事件发送
        self.event_handler.emit_tool_end.assert_awaited_once_with(
            'submission-5', 'invalid_tool', 'call-789', False, None, '工具不存在'
        )

    async def test_execute_turn_with_tool_returning_none(self):
        """测试工具返回None的处理"""
        
        tool_call = {
            'id': 'call-999',
            'type': 'function',
            'function': {
                'name': 'empty_tool',
                'arguments': '{}',
            },
        }
        
        response = ChatResponse(
            content='调用空工具',
            tool_calls=[tool_call],
            token_usage=TokenUsage(input_tokens=5, output_tokens=3, total_tokens=8),
            finish_reason='tool_calls',
        )
        self.model_client.chat_completion.return_value = response

        # 模拟工具返回None
        self.tool_registry.execute_tool.return_value = None

        result = await self.agent_turn.execute_turn('submission-6')

        # 验证None结果处理
        self.assertTrue(result.has_tool_calls())
        self.assertFalse(result.has_successful_tool_calls())
        self.assertEqual(len(result.tool_responses), 1)
        self.assertFalse(result.tool_responses[0].success)
        self.assertIn('执行失败或返回空结果', result.tool_responses[0].error)

    async def test_execute_turn_with_empty_response(self):
        """测试空响应的处理"""
        
        token_usage = TokenUsage(input_tokens=2, output_tokens=0, total_tokens=2)
        response = ChatResponse(
            content='',  # 空内容
            tool_calls=[],
            token_usage=token_usage,
            finish_reason='stop',
        )
        self.model_client.chat_completion.return_value = response

        result = await self.agent_turn.execute_turn('submission-7')

        # 验证空响应处理
        self.assertEqual(result.text_content, '')
        self.assertFalse(result.has_tool_calls())
        self.assertEqual(result.token_usage, token_usage)
        
        # 验证空响应时不添加assistant消息（因为既没有文本也没有工具调用）
        self.model_client.add_assistant_message.assert_not_called()
        
        # 验证不发送空消息事件
        self.event_handler.emit_agent_message.assert_not_awaited()

    async def test_execute_turn_without_event_handler(self):
        """测试没有事件处理器时的正常运行"""
        
        # 创建没有事件处理器的AgentTurn
        agent_turn = AgentTurn(
            model_client=self.model_client,
            tool_registry=self.tool_registry,
            event_handler=None,  # 无事件处理器
            session_id='session-test',
        )
        
        token_usage = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)
        response = ChatResponse(
            content='无事件处理器测试',
            tool_calls=[],
            token_usage=token_usage,
            finish_reason='stop',
        )
        self.model_client.chat_completion.return_value = response

        result = await agent_turn.execute_turn('submission-8')

        # 验证正常执行
        self.assertEqual(result.text_content, '无事件处理器测试')
        self.assertEqual(result.token_usage, token_usage)
        self.assertIsNotNone(result.duration_ms)
        
        # 验证assistant消息添加
        self.model_client.add_assistant_message.assert_called_once_with('无事件处理器测试', None)

    async def test_execute_turn_with_invalid_tool_call_json(self):
        """测试工具调用参数JSON解析失败的处理"""
        
        tool_call = {
            'id': 'call-invalid',
            'type': 'function',
            'function': {
                'name': 'test_tool',
                'arguments': '{"invalid": json}',  # 无效JSON
            },
        }
        
        response = ChatResponse(
            content='测试无效JSON',
            tool_calls=[tool_call],
            token_usage=TokenUsage(input_tokens=8, output_tokens=4, total_tokens=12),
            finish_reason='tool_calls',
        )
        self.model_client.chat_completion.return_value = response

        result = await self.agent_turn.execute_turn('submission-9')

        # 验证JSON解析错误被处理
        self.assertEqual(result.text_content, '测试无效JSON')
        # 由于JSON解析失败，工具调用不应被添加到结果中
        self.assertFalse(result.has_tool_calls())

    async def test_execute_turn_with_reasoning_content(self):
        """测试包含推理内容的响应处理"""
        
        # 创建带有推理内容的响应
        token_usage = TokenUsage(input_tokens=20, output_tokens=15, total_tokens=35)
        response = ChatResponse(
            content='基于推理的回答',
            tool_calls=[],
            token_usage=token_usage,
            finish_reason='stop',
        )
        # 手动添加推理内容属性
        response.reasoning_content = '这是推理过程的详细说明'
        
        self.model_client.chat_completion.return_value = response

        result = await self.agent_turn.execute_turn('submission-10')

        # 验证推理内容被正确解析
        self.assertEqual(result.text_content, '基于推理的回答')
        self.assertEqual(len(result.thoughts), 1)
        self.assertEqual(result.thoughts[0].subject, '推理')
        self.assertEqual(result.thoughts[0].description, '这是推理过程的详细说明')

    async def test_approval_workflow(self):
        """测试工具调用批准流程"""
        
        tool_call = {
            'id': 'call-approval',
            'type': 'function',
            'function': {
                'name': 'dangerous_tool',
                'arguments': '{"action": "delete_all"}',
            },
        }
        
        response = ChatResponse(
            content='需要批准的操作',
            tool_calls=[tool_call],
            token_usage=TokenUsage(input_tokens=12, output_tokens=8, total_tokens=20),
            finish_reason='tool_calls',
        )
        self.model_client.chat_completion.return_value = response

        # 模拟需要批准
        original_needs_approval = self.agent_turn._needs_approval
        self.agent_turn._needs_approval = AsyncMock(return_value=True)

        result = await self.agent_turn.execute_turn('submission-11')

        # 验证批准请求被发送
        self.agent_turn._needs_approval.assert_awaited_once_with(
            'dangerous_tool', {'action': 'delete_all'}
        )
        
        # 验证工具调用被添加但未执行（continue导致不会添加到tool_responses）
        self.assertTrue(result.has_tool_calls())
        self.assertEqual(len(result.tool_responses), 0)  # 未执行，等待批准
        
        # 验证批准请求在待处理列表中
        self.assertIn('call-approval', self.agent_turn.approval_pending)
        
        # 验证工具未被实际执行
        self.tool_registry.execute_tool.assert_not_awaited()
        
        # 恢复原方法
        self.agent_turn._needs_approval = original_needs_approval

    async def test_handle_approval_response_approved(self):
        """测试批准响应 - 同意执行"""
        
        # 设置待批准的工具调用
        self.agent_turn.approval_pending['call-approve-test'] = {
            "submission_id": "submission-12",
            "tool_name": "test_tool",
            "arguments": {"param": "value"},
            "call_id": "call-approve-test"
        }
        
        # 设置工具执行结果
        self.tool_registry.execute_tool.return_value = ToolResult(
            title='批准测试', output='执行成功'
        )

        # 处理批准响应
        result = await self.agent_turn.handle_approval_response('call-approve-test', True)

        # 验证批准处理成功
        self.assertTrue(result)
        
        # 验证工具被执行
        self.tool_registry.execute_tool.assert_awaited_once()
        
        # 验证结果添加到对话历史
        self.model_client.add_tool_message.assert_called_once_with(
            'call-approve-test', '执行成功'
        )
        
        # 验证待批准记录被清理
        self.assertNotIn('call-approve-test', self.agent_turn.approval_pending)

    async def test_handle_approval_response_rejected(self):
        """测试批准响应 - 拒绝执行"""
        
        # 设置待批准的工具调用
        self.agent_turn.approval_pending['call-reject-test'] = {
            "submission_id": "submission-13",
            "tool_name": "test_tool",
            "arguments": {"param": "value"},
            "call_id": "call-reject-test"
        }

        # 处理拒绝响应
        result = await self.agent_turn.handle_approval_response('call-reject-test', False)

        # 验证拒绝处理成功
        self.assertTrue(result)
        
        # 验证工具未被执行
        self.tool_registry.execute_tool.assert_not_awaited()
        
        # 验证拒绝消息添加到对话历史
        self.model_client.add_tool_message.assert_called_once_with(
            'call-reject-test', '用户拒绝执行工具调用: test_tool'
        )
        
        # 验证待批准记录被清理
        self.assertNotIn('call-reject-test', self.agent_turn.approval_pending)

    async def test_handle_approval_response_invalid_call_id(self):
        """测试批准响应 - 无效的call_id"""
        
        # 处理不存在的call_id
        result = await self.agent_turn.handle_approval_response('nonexistent-call', True)

        # 验证返回False
        self.assertFalse(result)
        
        # 验证没有任何操作
        self.tool_registry.execute_tool.assert_not_awaited()
        self.model_client.add_tool_message.assert_not_called()

    async def test_agent_turn_result_methods(self):
        """测试AgentTurnResult的辅助方法"""
        
        # 测试空结果
        empty_result = AgentTurnResult()
        self.assertFalse(empty_result.has_tool_calls())
        self.assertFalse(empty_result.has_successful_tool_calls())
        self.assertEqual(empty_result.get_summary(), "空响应")
        
        # 测试完整结果
        from core.agent_turn import ToolCallRequest, ToolCallResponse, ThoughtResult
        
        full_result = AgentTurnResult(
            text_content="测试响应",
            thoughts=[ThoughtResult("测试", "这是推理")],
            tool_calls=[ToolCallRequest("call-1", "test_tool", {})],
            tool_responses=[ToolCallResponse("call-1", True, "成功")],
            token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)
        )
        
        self.assertTrue(full_result.has_tool_calls())
        self.assertTrue(full_result.has_successful_tool_calls())
        summary = full_result.get_summary()
        self.assertIn("文本响应: 4 字符", summary)
        self.assertIn("推理内容: 1 条", summary)
        self.assertIn("工具调用: 1 个", summary)
        self.assertIn("Token: 15", summary)


if __name__ == '__main__':
    unittest.main()
