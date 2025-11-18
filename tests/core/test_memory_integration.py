"""测试记忆模块集成"""

import pytest
import tempfile
import asyncio
from pathlib import Path

from src.core.config import Config
from src.core.session import Session
from src.core.memory import MemoryManager


@pytest.fixture
def temp_session_dir():
    """临时会话目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_config(temp_session_dir):
    """测试配置"""
    return Config(
        model="test-model",
        api_key="test-key",
        api_base="https://test.api.com",
        cwd=Path.cwd() / "workspace",
        enable_memory=True,
        session_dir=temp_session_dir,
        auto_load_project_docs=False,  # 测试时关闭文档加载
        enable_compaction=False,  # 测试时关闭压缩
    )


def test_session_creates_memory_manager(test_config):
    """测试 Session 创建时初始化 MemoryManager"""
    session = Session(test_config)
    
    # 验证 memory_manager 已创建
    assert session.memory_manager is not None
    assert isinstance(session.memory_manager, MemoryManager)
    assert session.memory_manager.session_id == session.session_id
    assert session.memory_manager.rollout_path.exists()


def test_session_shares_memory_with_model_client(test_config):
    """测试 Session 和 ModelClient 共享 MemoryManager"""
    session = Session(test_config)
    
    # 验证 model_client 使用相同的 memory_manager
    assert session.model_client.memory_manager is session.memory_manager
    
    # 添加消息
    session.model_client.add_user_message("测试消息")
    
    # 验证消息已添加到 memory_manager
    assert len(session.memory_manager.messages) > 0
    user_messages = [m for m in session.memory_manager.messages if m.role == "user"]
    assert len(user_messages) == 1
    assert user_messages[0].content == "测试消息"


def test_session_persists_messages(test_config):
    """测试 Session 持久化消息到 JSONL"""
    session = Session(test_config)
    rollout_path = session.memory_manager.rollout_path
    
    # 添加几条消息
    session.model_client.add_user_message("消息1")
    session.model_client.add_assistant_message("回复1")
    session.model_client.add_user_message("消息2")
    
    # 验证文件存在且包含消息
    assert rollout_path.exists()
    content = rollout_path.read_text()
    assert "消息1" in content
    assert "回复1" in content
    assert "消息2" in content
    assert "session_meta" in content


def test_memory_manager_resume_session(test_config, temp_session_dir):
    """测试恢复会话"""
    # 1. 创建会话并添加消息
    session1 = Session(test_config)
    rollout_path = session1.memory_manager.rollout_path
    session_id = session1.session_id
    
    session1.model_client.add_user_message("会话1消息")
    session1.model_client.add_assistant_message("会话1回复")
    
    message_count = len(session1.memory_manager.messages)
    
    # 2. 恢复会话
    memory_manager2 = MemoryManager.resume_session(rollout_path)
    
    # 3. 验证恢复
    assert memory_manager2.session_id == session_id
    assert len(memory_manager2.messages) == message_count
    
    # 验证消息内容
    user_msgs = [m for m in memory_manager2.messages if m.role == "user" and m.content == "会话1消息"]
    assert len(user_msgs) == 1


def test_session_without_memory(temp_session_dir):
    """测试禁用记忆系统时的回退模式"""
    config = Config(
        model="test-model",
        api_key="test-key",
        api_base="https://test.api.com",
        cwd=Path.cwd() / "workspace",
        enable_memory=False,  # 禁用记忆
        session_dir=temp_session_dir,
    )
    
    session = Session(config)
    
    # 验证 memory_manager 为 None
    assert session.memory_manager is None
    assert session.model_client.memory_manager is None
    
    # 验证使用内部 conversation_history
    session.model_client.add_user_message("测试")
    assert len(session.model_client.conversation_history) > 0


def test_memory_manager_stats(test_config):
    """测试统计信息"""
    session = Session(test_config)
    
    session.model_client.add_user_message("测试统计")
    session.model_client.add_assistant_message("收到")
    session.model_client.add_tool_message("call_1", "工具结果")
    
    stats = session.memory_manager.get_stats()
    
    assert stats["session_id"] == session.session_id
    assert stats["user_messages"] == 1
    assert stats["assistant_messages"] == 1
    assert stats["tool_messages"] == 1
    assert stats["estimated_tokens"] > 0
    assert "rollout_path" in stats


def test_model_client_get_messages(test_config):
    """测试 ModelClient.get_messages() 统一接口"""
    session = Session(test_config)
    
    # 添加消息
    session.model_client.add_user_message("消息A")
    session.model_client.add_assistant_message("回复A", tool_calls=[{"id": "call_1"}])
    
    # 获取消息
    messages = session.model_client.get_messages()
    
    assert len(messages) > 0
    user_msgs = [m for m in messages if m.role == "user" and m.content == "消息A"]
    assert len(user_msgs) == 1
    
    assistant_msgs = [m for m in messages if m.role == "assistant" and m.content == "回复A"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].tool_calls is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

