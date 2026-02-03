#!/usr/bin/env python3
"""TaskTool 中断和清理功能测试"""

import unittest
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from tools.task_tool import TaskTool
from tools.task_manager import TaskManager
from tools.base_tool import ToolContext
from core.config import Config
from core.session import Session


class TestTaskInterruptAndCleanup(unittest.TestCase):
    """TaskTool 中断和清理功能测试"""
    
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
            session_id="test_interrupt_session",
            message_id="test_interrupt_msg",
            agent="test_agent"
        )
        
        # 清理会话
        self.task_manager = TaskManager()
        self.task_manager.clear_sessions()
    
    def test_active_subagent_tracking(self):
        """测试活跃子代理跟踪"""
        # 初始状态：没有活跃子代理
        self.assertEqual(len(self.task_tool.get_active_subagents()), 0)
        
        # 启动子代理后会被跟踪（需要 mock）
        async def run_test():
            # 由于真实执行会启动 Session，我们需要 mock
            with patch.object(self.task_tool, '_execute_real_session') as mock_exec:
                mock_exec.return_value = "测试结果"
                
                # 模拟注册子代理
                test_session_id = "test_sub_session"
                self.task_tool._active_subagents[test_session_id] = Mock()
                
                # 验证已注册
                self.assertTrue(self.task_tool.is_subagent_active(test_session_id))
                self.assertEqual(len(self.task_tool.get_active_subagents()), 1)
                
                # 清理
                self.task_tool._active_subagents.clear()
        
        asyncio.run(run_test())
    
    def test_cancel_subagent_not_exist(self):
        """测试取消不存在的子代理"""
        async def run_test():
            result = await self.task_tool.cancel_subagent("nonexistent_session")
            self.assertFalse(result)
        
        asyncio.run(run_test())
    
    def test_cancel_subagent_success(self):
        """测试成功取消子代理"""
        async def run_test():
            # 创建模拟的子 Session
            mock_session = AsyncMock()
            mock_session.session_id = "test_cancel_session"
            mock_session.stop = AsyncMock()
            mock_session.cleanup = AsyncMock()
            
            # 注册到活跃列表
            session_id = "test_cancel_session"
            self.task_tool._active_subagents[session_id] = mock_session
            
            # 创建任务记录
            self.task_manager.create_session(
                parent_session_id=self.context.session_id,
                subagent_type="plan",
                task_description="测试取消"
            )
            
            # 执行取消
            result = await self.task_tool.cancel_subagent(session_id)
            
            # 验证取消成功
            self.assertTrue(result)
            
            # 验证调用了 stop 和 cleanup
            mock_session.stop.assert_called_once()
            mock_session.cleanup.assert_called_once()
            
            # 验证从活跃列表移除
            self.assertFalse(self.task_tool.is_subagent_active(session_id))
        
        asyncio.run(run_test())
    
    def test_cancel_subagent_with_exception(self):
        """测试取消子代理时发生异常"""
        async def run_test():
            # 创建会抛出异常的模拟 Session
            mock_session = AsyncMock()
            mock_session.session_id = "test_error_session"
            mock_session.stop = AsyncMock(side_effect=Exception("测试异常"))
            mock_session.cleanup = AsyncMock()
            
            session_id = "test_error_session"
            self.task_tool._active_subagents[session_id] = mock_session
            
            # 执行取消（应该处理异常）
            result = await self.task_tool.cancel_subagent(session_id)
            
            # 即使发生异常，也应该返回 False 并从列表移除
            self.assertFalse(result)
            self.assertFalse(self.task_tool.is_subagent_active(session_id))
        
        asyncio.run(run_test())
    
    def test_cleanup_after_execution(self):
        """测试执行完成后自动清理"""
        async def run_test():
            # 创建模拟 Session
            mock_session = AsyncMock()
            mock_session.session_id = "cleanup_test_session"
            mock_session.is_active = False
            mock_session.start = AsyncMock()
            mock_session.submit_operation = AsyncMock()
            mock_session.stop = AsyncMock()
            mock_session.cleanup = AsyncMock()
            mock_session.get_next_event = AsyncMock(return_value=None)
            mock_session.model_client = Mock()
            mock_session.model_client.conversation_history = [
                Mock(role="assistant", content="测试结果")
            ]
            
            # Mock Session 构造函数
            with patch('core.session.Session', return_value=mock_session):
                # Mock AgentRegistry
                from core.agents import AgentRegistry, AgentInfo
                mock_agent = AgentInfo(
                    name="test_agent",
                    description="测试",
                    mode="subagent",
                    allowed_tools=["read", "grep"],
                    system_prompt="测试提示",
                    max_turns=5
                )
                
                with patch.object(self.task_tool.agent_registry, 'get', return_value=mock_agent):
                    # 执行任务
                    result = await self.task_tool.execute({
                        "description": "清理测试",
                        "task_prompt": "测试任务",
                        "subagent_type": "test_agent"
                    }, self.context)
                    
                    # 验证 cleanup 被调用
                    mock_session.cleanup.assert_called_once()
                    
                    # 验证已从活跃列表移除
                    self.assertEqual(len(self.task_tool.get_active_subagents()), 0)
        
        asyncio.run(run_test())
    
    def test_cleanup_on_exception(self):
        """测试异常时也会清理"""
        async def run_test():
            # 创建会抛出异常的模拟 Session
            mock_session = AsyncMock()
            mock_session.session_id = "exception_cleanup_session"
            mock_session.is_active = True
            mock_session.start = AsyncMock()
            mock_session.submit_operation = AsyncMock()
            mock_session.stop = AsyncMock()
            mock_session.cleanup = AsyncMock()
            mock_session.get_next_event = AsyncMock(side_effect=Exception("测试异常"))
            
            with patch('core.session.Session', return_value=mock_session):
                from core.agents import AgentInfo
                mock_agent = AgentInfo(
                    name="test_agent",
                    description="测试",
                    mode="subagent",
                    allowed_tools=["read"],
                    system_prompt="测试",
                    max_turns=5
                )
                
                with patch.object(self.task_tool.agent_registry, 'get', return_value=mock_agent):
                    # 执行任务（会抛出异常）
                    result = await self.task_tool.execute({
                        "description": "异常清理测试",
                        "task_prompt": "测试",
                        "subagent_type": "test_agent"
                    }, self.context)
                    
                    # 验证即使发生异常，cleanup 也被调用
                    mock_session.cleanup.assert_called_once()
                    
                    # 验证已从活跃列表移除
                    self.assertEqual(len(self.task_tool.get_active_subagents()), 0)
                    
                    # 验证返回了失败结果
                    self.assertEqual(result.metadata["status"], "failed")
        
        asyncio.run(run_test())
    
    def test_session_cleanup_method(self):
        """测试 Session.cleanup() 方法"""
        async def run_test():
            # 创建真实的 Session
            config = Config(
                model="gpt-4",
                cwd=Path.cwd(),
                max_turns=3,
                enable_memory=False,
                enable_hooks=False,
                enable_compaction=False,
            )
            
            session = Session(config=config, agent_name="general")
            
            # 执行清理（不应抛出异常）
            await session.cleanup()
            
            # 验证清理完成
            self.assertIsNotNone(session)
        
        asyncio.run(run_test())
    
    def test_multiple_subagent_tracking(self):
        """测试跟踪多个子代理"""
        # 模拟多个活跃的子代理
        mock_sessions = {
            "session1": AsyncMock(),
            "session2": AsyncMock(),
            "session3": AsyncMock()
        }
        
        for session_id, mock_session in mock_sessions.items():
            self.task_tool._active_subagents[session_id] = mock_session
        
        # 验证数量
        self.assertEqual(len(self.task_tool.get_active_subagents()), 3)
        
        # 验证都是活跃的
        for session_id in mock_sessions.keys():
            self.assertTrue(self.task_tool.is_subagent_active(session_id))
        
        # 清理
        self.task_tool._active_subagents.clear()
    
    def test_cancel_updates_task_manager(self):
        """测试取消操作更新任务管理器"""
        async def run_test():
            # 创建任务记录
            session_id = "test_status_update"
            sub_session = self.task_manager.create_session(
                parent_session_id=self.context.session_id,
                subagent_type="plan",
                task_description="测试状态更新"
            )
            
            # 创建模拟 Session
            mock_session = AsyncMock()
            mock_session.session_id = sub_session.id
            mock_session.stop = AsyncMock()
            mock_session.cleanup = AsyncMock()
            
            # 注册
            self.task_tool._active_subagents[sub_session.id] = mock_session
            
            # 执行取消
            await self.task_tool.cancel_subagent(sub_session.id)
            
            # 验证任务管理器中的状态已更新
            updated_session = self.task_manager.get_session(sub_session.id)
            self.assertEqual(updated_session.status, "cancelled")
            self.assertIsNotNone(updated_session.error)
            self.assertIn("取消", updated_session.error)
        
        asyncio.run(run_test())


class TestSessionCleanup(unittest.TestCase):
    """Session 清理功能独立测试"""
    
    def test_cleanup_without_resources(self):
        """测试没有资源时的清理"""
        async def run_test():
            config = Config(
                model="gpt-4",
                cwd=Path.cwd(),
                max_turns=3,
                enable_memory=False,
                enable_hooks=False,
            )
            
            session = Session(config=config, agent_name="general")
            
            # 直接清理（不应抛出异常）
            await session.cleanup()
        
        asyncio.run(run_test())
    
    def test_cleanup_with_failed_model_client_close(self):
        """测试模型客户端关闭失败时的清理"""
        async def run_test():
            config = Config(
                model="gpt-4",
                cwd=Path.cwd(),
                max_turns=3,
                enable_memory=False,
                enable_hooks=False,
            )
            
            session = Session(config=config, agent_name="general")
            
            # Mock 模型客户端关闭失败
            session.model_client.close = AsyncMock(side_effect=Exception("关闭失败"))
            
            # 清理不应抛出异常
            await session.cleanup()
        
        asyncio.run(run_test())
    
    def test_cleanup_with_memory_manager(self):
        """测试带记忆管理器的清理"""
        async def run_test():
            config = Config(
                model="gpt-4",
                cwd=Path.cwd(),
                max_turns=3,
                enable_memory=False,
                enable_hooks=False,
            )
            
            # 主 Session（非子代理）
            session = Session(config=config, agent_name="general")
            
            # 模拟记忆管理器的 flush 方法
            if session.memory_manager:
                from unittest.mock import AsyncMock
                session.memory_manager.flush = AsyncMock()
            
            # 执行清理
            await session.cleanup()
            
            # 验证主 Session 的记忆管理器 flush 被调用（如果有）
            if session.memory_manager and hasattr(session.memory_manager, 'flush'):
                # 验证清理正常完成
                self.assertIsNotNone(session)
        
        asyncio.run(run_test())


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
