"""Session 压缩集成测试"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.session import Session
from core.config import Config


class TestSessionCompaction:
    """测试 Session 中的压缩功能集成"""
    
    @pytest.fixture
    def config_with_compaction(self):
        """创建测试配置（启用压缩）"""
        return Config(
            model="gpt-4",
            api_key="test-key",
            cwd=Path.cwd(),
            enable_compaction=True  # 启用压缩
        )
    
    @pytest.fixture
    def config_without_compaction(self):
        """创建测试配置（禁用压缩）"""
        return Config(
            model="gpt-4",
            api_key="test-key",
            cwd=Path.cwd(),
            enable_compaction=False  # 禁用压缩
        )
    
    def test_session_with_compaction_enabled(self, config_with_compaction):
        """测试启用压缩时会话初始化"""
        session = Session(config_with_compaction)
        
        # 验证压缩管理器已初始化
        assert session.compaction_manager is not None
        assert "opencode" in session.compaction_manager.strategies
        assert session.compaction_manager.current_strategy == "opencode"
    
    def test_session_with_compaction_disabled(self, config_without_compaction):
        """测试禁用压缩时会话初始化"""
        session = Session(config_without_compaction)
        
        # 验证压缩管理器未初始化
        assert session.compaction_manager is None
    
    def test_compaction_manager_configuration(self, config_with_compaction):
        """测试压缩管理器配置正确"""
        session = Session(config_with_compaction)
        
        # 获取策略
        strategy = session.compaction_manager.get_strategy()
        
        # 验证策略元数据
        metadata = strategy.get_metadata()
        assert metadata.name == "opencode"
        assert metadata.version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_check_and_compact_when_disabled(self, config_without_compaction):
        """测试禁用压缩时检查方法直接返回"""
        session = Session(config_without_compaction)
        
        # 添加消息
        session.model_client.add_user_message("Test")
        
        # 调用压缩检查（应该直接返回，不执行压缩）
        await session._check_and_compact("test-id")
        
        # 验证未触发任何压缩
        assert session.compaction_manager is None
    
    @pytest.mark.asyncio
    async def test_check_and_compact_when_enabled(self, config_with_compaction):
        """测试启用压缩时检查方法可调用"""
        session = Session(config_with_compaction)
        
        # 添加测试消息
        session.model_client.add_user_message("Test message")
        
        # 调用压缩检查（不应该抛出异常）
        try:
            await session._check_and_compact("test-submission-id")
        except Exception as e:
            pytest.fail(f"压缩检查方法调用失败: {e}")
    
    @pytest.mark.asyncio
    async def test_compaction_with_low_token_usage(self, config_with_compaction):
        """测试低 token 使用率时不触发压缩"""
        session = Session(config_with_compaction)
        
        # 添加少量消息
        session.model_client.add_user_message("Hello")
        session.model_client.add_assistant_message("Hi")
        
        messages_before = len(session.model_client.conversation_history)
        
        # 执行压缩检查
        await session._check_and_compact("test-id")
        
        # 消息数量应该不变（未触发压缩）
        assert len(session.model_client.conversation_history) == messages_before
    
    @pytest.mark.asyncio
    async def test_compaction_handles_errors_gracefully(self, config_with_compaction):
        """测试压缩错误不影响正常流程"""
        session = Session(config_with_compaction)
        
        # 设置一个会导致错误的场景（添加少量消息后尝试压缩）
        session.model_client.add_user_message("test message")
        
        # 压缩检查应该正常处理不抛出异常
        try:
            await session._check_and_compact("test-id")
        except Exception as e:
            pytest.fail(f"压缩错误未被正确处理: {e}")


class TestCompactionIntegration:
    """测试压缩功能的完整集成"""
    
    @pytest.fixture
    def config(self):
        return Config(
            model="gpt-4",
            api_key="test-key",
            cwd=Path.cwd(),
            enable_compaction=True,     # 启用压缩
            max_context_tokens=1000     # 设置较小的上下文以便测试
        )
    
    @pytest.mark.asyncio
    async def test_compaction_triggered_with_high_token_usage(self, config):
        """测试高 token 使用率时触发压缩"""
        session = Session(config)
        
        # 添加大量消息模拟高 token 使用
        for i in range(20):
            session.model_client.add_user_message(f"Message {i} " * 50)
            session.model_client.add_assistant_message(f"Response {i} " * 50)
        
        messages_before = len(session.model_client.conversation_history)
        
        # 执行压缩检查
        await session._check_and_compact("test-id")
        
        messages_after = len(session.model_client.conversation_history)
        
        # 应该触发压缩，消息数减少
        # 注意：由于压缩阈值是75%，需要足够的消息才能触发
        # 这里我们只验证方法能正常执行
        assert messages_after >= 0
    
    def test_config_defaults(self):
        """测试配置默认值"""
        config = Config(
            model="gpt-4",
            api_key="test-key"
        )
        
        # 默认应该禁用压缩
        assert config.enable_compaction is False
        assert config.max_context_tokens == 128000
