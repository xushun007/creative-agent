#!/usr/bin/env python3
"""TaskManager 单元测试"""

import unittest
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from tools.task_manager import TaskManager, SubagentConfig, SubagentSession


class TestSubagentConfig(unittest.TestCase):
    """SubagentConfig 测试"""
    
    def test_create_subagent_config(self):
        """测试创建子代理配置"""
        config = SubagentConfig(
            name="test_agent",
            description="测试代理",
            system_prompt="你是一个测试代理",
            allowed_tools=["read", "write"],
            max_turns=5,
            temperature=0.8,
            model_override="gpt-4"
        )
        
        self.assertEqual(config.name, "test_agent")
        self.assertEqual(config.description, "测试代理")
        self.assertEqual(config.system_prompt, "你是一个测试代理")
        self.assertEqual(config.allowed_tools, ["read", "write"])
        self.assertEqual(config.max_turns, 5)
        self.assertEqual(config.temperature, 0.8)
        self.assertEqual(config.model_override, "gpt-4")
    
    def test_subagent_config_defaults(self):
        """测试子代理配置默认值"""
        config = SubagentConfig(
            name="minimal",
            description="最小配置",
            system_prompt="系统提示",
            allowed_tools=["read"]
        )
        
        self.assertEqual(config.max_turns, 10)
        self.assertEqual(config.temperature, 0.7)
        self.assertIsNone(config.model_override)


class TestSubagentSession(unittest.TestCase):
    """SubagentSession 测试"""
    
    def test_create_subagent_session(self):
        """测试创建子代理会话"""
        now = datetime.now()
        session = SubagentSession(
            id="session_123",
            parent_session_id="parent_456",
            subagent_type="plan",
            task_description="规划任务",
            status="running",
            created_at=now
        )
        
        self.assertEqual(session.id, "session_123")
        self.assertEqual(session.parent_session_id, "parent_456")
        self.assertEqual(session.subagent_type, "plan")
        self.assertEqual(session.task_description, "规划任务")
        self.assertEqual(session.status, "running")
        self.assertEqual(session.created_at, now)
        self.assertIsNone(session.completed_at)
        self.assertIsNone(session.result)
        self.assertIsNone(session.error)
    
    def test_session_with_result(self):
        """测试带结果的会话"""
        session = SubagentSession(
            id="session_789",
            parent_session_id="parent_456",
            subagent_type="explore",
            task_description="探索代码",
            status="completed",
            created_at=datetime.now(),
            completed_at=datetime.now(),
            result="探索完成，发现3个关键文件"
        )
        
        self.assertEqual(session.status, "completed")
        self.assertIsNotNone(session.completed_at)
        self.assertIsNotNone(session.result)


class TestTaskManager(unittest.TestCase):
    """TaskManager 测试"""
    
    def setUp(self):
        """测试前准备"""
        self.manager = TaskManager()
        # 清空会话记录
        self.manager.clear_sessions()
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = TaskManager()
        manager2 = TaskManager()
        
        self.assertIs(manager1, manager2)
    
    def test_register_subagent(self):
        """测试注册子代理"""
        config = SubagentConfig(
            name="test_agent",
            description="测试代理",
            system_prompt="系统提示",
            allowed_tools=["read"]
        )
        
        self.manager.register_subagent(config)
        
        # 验证可以获取
        retrieved = self.manager.get_subagent("test_agent")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "test_agent")
        self.assertEqual(retrieved.description, "测试代理")
    
    def test_register_duplicate_subagent(self):
        """测试重复注册子代理（应该覆盖）"""
        config1 = SubagentConfig(
            name="test_agent",
            description="描述1",
            system_prompt="提示1",
            allowed_tools=["read"]
        )
        
        config2 = SubagentConfig(
            name="test_agent",
            description="描述2",
            system_prompt="提示2",
            allowed_tools=["write"]
        )
        
        self.manager.register_subagent(config1)
        self.manager.register_subagent(config2)
        
        # 应该是最新的配置
        retrieved = self.manager.get_subagent("test_agent")
        self.assertEqual(retrieved.description, "描述2")
        self.assertEqual(retrieved.allowed_tools, ["write"])
    
    def test_get_nonexistent_subagent(self):
        """测试获取不存在的子代理"""
        result = self.manager.get_subagent("nonexistent")
        self.assertIsNone(result)
    
    def test_list_subagents(self):
        """测试列出所有子代理"""
        config1 = SubagentConfig(
            name="agent1",
            description="代理1",
            system_prompt="提示1",
            allowed_tools=["read"]
        )
        
        config2 = SubagentConfig(
            name="agent2",
            description="代理2",
            system_prompt="提示2",
            allowed_tools=["write"]
        )
        
        self.manager.register_subagent(config1)
        self.manager.register_subagent(config2)
        
        agents = self.manager.list_subagents()
        agent_names = [a.name for a in agents]
        
        self.assertIn("agent1", agent_names)
        self.assertIn("agent2", agent_names)
    
    def test_create_session(self):
        """测试创建会话"""
        session = self.manager.create_session(
            parent_session_id="parent_123",
            subagent_type="plan",
            task_description="规划测试"
        )
        
        self.assertIsNotNone(session.id)
        self.assertTrue(session.id.startswith("task_"))
        self.assertEqual(session.parent_session_id, "parent_123")
        self.assertEqual(session.subagent_type, "plan")
        self.assertEqual(session.task_description, "规划测试")
        self.assertEqual(session.status, "running")
    
    def test_get_session(self):
        """测试获取会话"""
        session = self.manager.create_session(
            parent_session_id="parent_456",
            subagent_type="explore",
            task_description="探索测试"
        )
        
        retrieved = self.manager.get_session(session.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, session.id)
        self.assertEqual(retrieved.subagent_type, "explore")
    
    def test_get_nonexistent_session(self):
        """测试获取不存在的会话"""
        result = self.manager.get_session("nonexistent_id")
        self.assertIsNone(result)
    
    def test_update_session_status(self):
        """测试更新会话状态"""
        session = self.manager.create_session(
            parent_session_id="parent_789",
            subagent_type="general",
            task_description="通用任务"
        )
        
        # 更新为完成状态
        self.manager.update_session_status(
            session.id,
            status="completed",
            result="任务完成"
        )
        
        updated = self.manager.get_session(session.id)
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.result, "任务完成")
        self.assertIsNotNone(updated.completed_at)
    
    def test_update_session_with_error(self):
        """测试更新会话失败状态"""
        session = self.manager.create_session(
            parent_session_id="parent_000",
            subagent_type="plan",
            task_description="失败任务"
        )
        
        self.manager.update_session_status(
            session.id,
            status="failed",
            error="执行失败"
        )
        
        updated = self.manager.get_session(session.id)
        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.error, "执行失败")
        self.assertIsNotNone(updated.completed_at)
    
    def test_list_sessions(self):
        """测试列出所有会话"""
        session1 = self.manager.create_session(
            parent_session_id="parent_aaa",
            subagent_type="plan",
            task_description="任务1"
        )
        
        session2 = self.manager.create_session(
            parent_session_id="parent_aaa",
            subagent_type="explore",
            task_description="任务2"
        )
        
        all_sessions = self.manager.list_sessions()
        self.assertGreaterEqual(len(all_sessions), 2)
        
        session_ids = [s.id for s in all_sessions]
        self.assertIn(session1.id, session_ids)
        self.assertIn(session2.id, session_ids)
    
    def test_list_sessions_by_parent(self):
        """测试按父会话ID过滤会话"""
        session1 = self.manager.create_session(
            parent_session_id="parent_bbb",
            subagent_type="plan",
            task_description="任务1"
        )
        
        session2 = self.manager.create_session(
            parent_session_id="parent_bbb",
            subagent_type="explore",
            task_description="任务2"
        )
        
        session3 = self.manager.create_session(
            parent_session_id="parent_ccc",
            subagent_type="general",
            task_description="任务3"
        )
        
        # 过滤 parent_bbb 的会话
        filtered = self.manager.list_sessions(parent_session_id="parent_bbb")
        self.assertEqual(len(filtered), 2)
        
        session_ids = [s.id for s in filtered]
        self.assertIn(session1.id, session_ids)
        self.assertIn(session2.id, session_ids)
        self.assertNotIn(session3.id, session_ids)
    
    def test_clear_sessions(self):
        """测试清空会话"""
        self.manager.create_session(
            parent_session_id="parent_ddd",
            subagent_type="plan",
            task_description="任务1"
        )
        
        self.manager.create_session(
            parent_session_id="parent_ddd",
            subagent_type="explore",
            task_description="任务2"
        )
        
        # 清空前应该有会话
        self.assertGreater(len(self.manager.list_sessions()), 0)
        
        # 清空
        self.manager.clear_sessions()
        
        # 清空后应该没有会话
        self.assertEqual(len(self.manager.list_sessions()), 0)


if __name__ == "__main__":
    unittest.main()
