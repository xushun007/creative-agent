"""测试 CLI Resume 功能

测试 codex sessions 和 codex resume 命令的核心功能
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.core.config import Config
from src.core.session import Session
from src.core.memory import MemoryManager


@pytest.fixture
def temp_session_dir():
    """创建临时会话目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir) / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        yield session_dir


@pytest.fixture
def test_sessions(temp_session_dir):
    """创建测试会话"""
    sessions_info = []
    
    for i in range(3):
        config = Config(
            model=f"test-model-{i}",
            api_key="test-key",
            api_base="https://test.api.com",
            cwd=Path.cwd() / f"test-workspace-{i}",
            enable_memory=True,
            session_dir=temp_session_dir,
            auto_load_project_docs=False
        )
        
        session = Session(config)
        
        # 添加测试消息
        session.model_client.add_user_message(f"测试消息 {i}")
        session.model_client.add_assistant_message(f"收到消息 {i}")
        
        sessions_info.append({
            'session_id': session.session_id,
            'config': config,
            'session': session
        })
    
    return sessions_info


def test_list_sessions(test_sessions, temp_session_dir):
    """测试列出会话功能"""
    # 列出所有会话
    all_sessions = MemoryManager.list_sessions(temp_session_dir)
    
    # 验证会话数量
    assert len(all_sessions) == 3, f"期望 3 个会话，实际 {len(all_sessions)} 个"
    
    # 验证会话按时间倒序排列
    for i in range(len(all_sessions) - 1):
        _, meta1 = all_sessions[i]
        _, meta2 = all_sessions[i + 1]
        assert meta1.created_at >= meta2.created_at, "会话未按时间倒序排列"
    
    # 验证会话元数据
    for rollout_path, meta in all_sessions:
        assert rollout_path.exists(), f"Rollout 文件不存在: {rollout_path}"
        assert meta.session_id, "会话 ID 为空"
        assert meta.model.startswith("test-model-"), f"模型名称不正确: {meta.model}"
        assert isinstance(meta.created_at, datetime), "创建时间类型不正确"


def test_resume_session(test_sessions, temp_session_dir):
    """测试恢复会话功能"""
    # 获取第一个会话
    all_sessions = MemoryManager.list_sessions(temp_session_dir)
    assert len(all_sessions) > 0, "没有可用的会话"
    
    rollout_path, original_meta = all_sessions[0]
    
    # 恢复会话
    memory_manager = MemoryManager.resume_session(rollout_path)
    
    # 验证恢复的数据
    assert memory_manager.session_id == original_meta.session_id, "会话 ID 不匹配"
    
    # 验证消息数量
    stats = memory_manager.get_stats()
    assert stats['total_messages'] >= 2, f"消息数量不足: {stats['total_messages']}"
    assert stats['user_messages'] >= 1, f"用户消息数量不足: {stats['user_messages']}"
    assert stats['assistant_messages'] >= 1, f"助手消息数量不足: {stats['assistant_messages']}"
    
    # 验证消息内容
    messages = memory_manager.messages
    assert len(messages) > 0, "没有加载任何消息"
    
    # 查找用户消息
    user_messages = [msg for msg in messages if msg.role == "user"]
    assert len(user_messages) > 0, "没有用户消息"
    
    # 验证消息内容包含 "测试消息"
    user_contents = [msg.content for msg in user_messages]
    assert any("测试消息" in content for content in user_contents), "未找到测试消息内容"


def test_session_id_prefix_match(test_sessions, temp_session_dir):
    """测试会话 ID 前缀匹配"""
    all_sessions = MemoryManager.list_sessions(temp_session_dir)
    assert len(all_sessions) > 0, "没有可用的会话"
    
    # 获取第一个会话的 ID 前缀
    _, meta = all_sessions[0]
    session_id_prefix = meta.session_id[:8]
    
    # 查找匹配的会话
    found = False
    for _, m in all_sessions:
        if m.session_id.startswith(session_id_prefix):
            found = True
            assert m.session_id == meta.session_id, "前缀匹配到错误的会话"
            break
    
    assert found, f"未找到前缀为 {session_id_prefix} 的会话"


def test_empty_session_dir():
    """测试空会话目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_dir = Path(tmpdir) / "empty_sessions"
        empty_dir.mkdir(parents=True, exist_ok=True)
        
        all_sessions = MemoryManager.list_sessions(empty_dir)
        assert len(all_sessions) == 0, "空目录应该返回空列表"


def test_resume_with_multiple_messages(temp_session_dir):
    """测试恢复包含多条消息的会话"""
    # 创建一个会话并添加多条消息
    config = Config(
        model="test-model",
        api_key="test-key",
        api_base="https://test.api.com",
        cwd=Path.cwd() / "test-workspace",
        enable_memory=True,
        session_dir=temp_session_dir,
        auto_load_project_docs=False
    )
    
    session = Session(config)
    
    # 添加多轮对话
    for i in range(5):
        session.model_client.add_user_message(f"用户消息 {i}")
        session.model_client.add_assistant_message(f"助手回复 {i}")
    
    # 恢复会话
    all_sessions = MemoryManager.list_sessions(temp_session_dir)
    rollout_path, _ = all_sessions[0]
    
    memory_manager = MemoryManager.resume_session(rollout_path)
    
    # 验证消息数量
    stats = memory_manager.get_stats()
    assert stats['user_messages'] == 5, f"期望 5 条用户消息，实际 {stats['user_messages']} 条"
    assert stats['assistant_messages'] == 5, f"期望 5 条助手消息，实际 {stats['assistant_messages']} 条"
    
    # 验证消息顺序
    messages = memory_manager.messages
    user_msgs = [msg for msg in messages if msg.role == "user"]
    assistant_msgs = [msg for msg in messages if msg.role == "assistant"]
    
    # 验证内容
    for i, msg in enumerate(user_msgs):
        assert f"用户消息 {i}" in msg.content, f"用户消息 {i} 内容不正确"
    
    for i, msg in enumerate(assistant_msgs):
        assert f"助手回复 {i}" in msg.content, f"助手消息 {i} 内容不正确"


def test_session_stats_accuracy(test_sessions, temp_session_dir):
    """测试会话统计信息的准确性"""
    all_sessions = MemoryManager.list_sessions(temp_session_dir)
    
    for rollout_path, meta in all_sessions:
        memory_manager = MemoryManager.resume_session(rollout_path)
        stats = memory_manager.get_stats()
        
        # 验证统计信息字段存在
        assert 'total_messages' in stats, "缺少 total_messages 字段"
        assert 'user_messages' in stats, "缺少 user_messages 字段"
        assert 'assistant_messages' in stats, "缺少 assistant_messages 字段"
        assert 'estimated_tokens' in stats, "缺少 estimated_tokens 字段"
        
        # 验证数量关系
        user_count = stats['user_messages']
        assistant_count = stats['assistant_messages']
        system_count = stats.get('system_messages', 0)
        tool_count = stats.get('tool_messages', 0)
        
        expected_total = user_count + assistant_count + system_count + tool_count
        actual_total = stats['total_messages']
        
        assert actual_total == expected_total, \
            f"总消息数不匹配: 期望 {expected_total}, 实际 {actual_total}"
        
        # 验证 tokens 估算是正数
        assert stats['estimated_tokens'] > 0, "估算 tokens 应该大于 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

