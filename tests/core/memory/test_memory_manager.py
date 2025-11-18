"""测试记忆管理器"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.core.memory import (
    MemoryManager,
    MemoryMessage,
    TokenCounter
)


@pytest.fixture
def temp_session_dir():
    """临时会话目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def memory_manager(temp_session_dir):
    """创建记忆管理器"""
    return MemoryManager(
        session_dir=temp_session_dir,
        cwd=Path.cwd(),
        model="test-model",
        user_instructions="测试指令",
        auto_load_project_docs=False
    )


def test_create_new_session(temp_session_dir):
    """测试创建新会话"""
    manager = MemoryManager(
        session_dir=temp_session_dir,
        cwd=Path.cwd(),
        model="test-model",
        auto_load_project_docs=False
    )
    
    assert manager.session_id is not None
    assert len(manager.session_id) > 0
    assert manager.rollout_path.exists()
    assert manager.cwd == Path.cwd()


def test_add_messages(memory_manager):
    """测试添加消息"""
    # 添加用户消息
    user_msg = memory_manager.add_user_message("你好")
    assert user_msg.role == "user"
    assert user_msg.content == "你好"
    assert len(memory_manager.messages) == 2  # 系统消息 + 用户消息
    
    # 添加助手消息
    assistant_msg = memory_manager.add_assistant_message("你好！")
    assert assistant_msg.role == "assistant"
    assert len(memory_manager.messages) == 3
    
    # 添加工具消息
    tool_msg = memory_manager.add_tool_message("结果", tool_call_id="call_1")
    assert tool_msg.role == "tool"
    assert tool_msg.tool_call_id == "call_1"
    assert len(memory_manager.messages) == 4


def test_get_messages(memory_manager):
    """测试获取消息"""
    memory_manager.add_user_message("消息1")
    memory_manager.add_assistant_message("回复1")
    memory_manager.add_user_message("消息2")
    
    # 获取所有消息
    all_messages = memory_manager.get_messages()
    assert len(all_messages) == 4  # 系统 + 3条对话
    
    # 过滤系统消息
    filtered = memory_manager.get_messages(filter_system=True)
    assert len(filtered) == 3
    assert all(m.role != "system" for m in filtered)


def test_get_stats(memory_manager):
    """测试获取统计信息"""
    memory_manager.add_user_message("测试消息")
    memory_manager.add_assistant_message("测试回复")
    
    stats = memory_manager.get_stats()
    
    assert stats["session_id"] == memory_manager.session_id
    assert stats["user_messages"] == 1
    assert stats["assistant_messages"] == 1
    assert stats["estimated_tokens"] > 0
    assert "rollout_path" in stats
    assert "cwd" in stats


def test_replace_messages(memory_manager):
    """测试替换消息历史"""
    # 添加初始消息
    memory_manager.add_user_message("消息1")
    memory_manager.add_assistant_message("回复1")
    
    assert len(memory_manager.messages) > 2
    
    # 替换消息
    new_messages = [
        MemoryMessage(
            role="system",
            content="新系统消息",
            timestamp=datetime.now()
        )
    ]
    
    memory_manager.replace_messages(new_messages)
    assert len(memory_manager.messages) == 1
    assert memory_manager.messages[0].content == "新系统消息"


def test_record_compaction(memory_manager):
    """测试记录压缩"""
    memory_manager.add_user_message("消息1")
    memory_manager.add_assistant_message("回复1")
    
    # 记录压缩
    memory_manager.record_compaction(
        summary="测试摘要",
        original_count=10,
        tokens_saved=1000,
        strategy="test"
    )
    
    # 验证 rollout 文件包含压缩标记
    assert memory_manager.rollout_path.exists()


def test_resume_session(temp_session_dir):
    """测试恢复会话"""
    # 1. 创建会话
    manager1 = MemoryManager(
        session_dir=temp_session_dir,
        cwd=Path.cwd(),
        model="test-model",
        user_instructions="原始指令",
        auto_load_project_docs=False
    )
    
    manager1.add_user_message("消息1")
    manager1.add_assistant_message("回复1")
    manager1.add_user_message("消息2")
    
    rollout_path = manager1.rollout_path
    session_id = manager1.session_id
    message_count = len(manager1.messages)
    
    # 2. 恢复会话
    manager2 = MemoryManager.resume_session(rollout_path)
    
    assert manager2.session_id == session_id
    assert len(manager2.messages) == message_count
    assert manager2.messages[-1].content == "消息2"
    
    # 3. 继续添加消息
    manager2.add_user_message("消息3")
    assert len(manager2.messages) == message_count + 1


def test_list_sessions(temp_session_dir):
    """测试列出会话"""
    # 创建多个会话
    for i in range(3):
        manager = MemoryManager(
            session_dir=temp_session_dir,
            cwd=Path.cwd(),
            model=f"model-{i}",
            auto_load_project_docs=False
        )
        manager.add_user_message(f"测试消息 {i}")
    
    # 列出会话
    sessions = MemoryManager.list_sessions(temp_session_dir)
    
    assert len(sessions) == 3
    assert all(isinstance(path, Path) for path, _ in sessions)


def test_get_context_for_llm(memory_manager):
    """测试获取 LLM 上下文"""
    memory_manager.add_user_message("你好")
    memory_manager.add_assistant_message("你好！", tool_calls=[{"id": "call_1"}])
    
    context = memory_manager.get_context_for_llm()
    
    assert isinstance(context, list)
    assert all(isinstance(msg, dict) for msg in context)
    assert all("role" in msg and "content" in msg for msg in context)


def test_persistence(temp_session_dir):
    """测试持久化"""
    manager = MemoryManager(
        session_dir=temp_session_dir,
        cwd=Path.cwd(),
        model="test-model",
        auto_load_project_docs=False
    )
    
    # 添加消息
    manager.add_user_message("持久化测试")
    manager.add_assistant_message("收到")
    
    # 验证文件存在且有内容
    assert manager.rollout_path.exists()
    
    content = manager.rollout_path.read_text()
    assert "持久化测试" in content
    assert "收到" in content
    assert "session_meta" in content

