"""CompactionManager 单元测试"""

import sys
from pathlib import Path
import pytest

# 添加 src 到路径以避免触发 src.core.__init__ 的导入链
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from core.compaction.manager import CompactionManager
from core.compaction.strategies.opencode import OpenCodeStrategy
from core.compaction.base import CompactionContext


class TestCompactionManager:
    """CompactionManager 测试"""
    
    @pytest.fixture
    def manager(self):
        """创建管理器实例"""
        return CompactionManager()
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return OpenCodeStrategy()
    
    @pytest.fixture
    def context(self):
        """创建测试上下文"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well!"}
        ]
        
        return CompactionContext(
            messages=messages,
            current_tokens=100000,
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test-session"
        )
    
    def test_register_strategy(self, manager, strategy):
        """测试：注册策略"""
        manager.register_strategy("opencode", strategy)
        
        assert "opencode" in manager.strategies
        assert "opencode" in manager.metrics
    
    def test_set_strategy(self, manager, strategy):
        """测试：设置当前策略"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        assert manager.current_strategy == "opencode"
    
    def test_set_nonexistent_strategy_raises_error(self, manager):
        """测试：设置不存在的策略抛出异常"""
        with pytest.raises(ValueError, match="不存在"):
            manager.set_strategy("nonexistent")
    
    def test_get_strategy(self, manager, strategy):
        """测试：获取策略实例"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        retrieved = manager.get_strategy()
        
        assert retrieved is strategy
    
    def test_get_strategy_by_name(self, manager, strategy):
        """测试：按名称获取策略"""
        manager.register_strategy("opencode", strategy)
        
        retrieved = manager.get_strategy("opencode")
        
        assert retrieved is strategy
    
    def test_get_strategy_without_selection_raises_error(self, manager):
        """测试：未选择策略时获取抛出异常"""
        with pytest.raises(ValueError, match="没有选择策略"):
            manager.get_strategy()
    
    @pytest.mark.asyncio
    async def test_check_and_compact_when_needed(self, manager, strategy, context):
        """测试：需要时执行压缩"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        result = await manager.check_and_compact(context)
        
        assert result is not None
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_check_and_compact_when_not_needed(self, manager, strategy):
        """测试：不需要时不执行压缩"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        # 低于阈值的上下文
        context = CompactionContext(
            messages=[],
            current_tokens=50000,  # 低于75%阈值
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test"
        )
        
        result = await manager.check_and_compact(context)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_force_compact(self, manager, strategy):
        """测试：强制压缩"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        # 低于阈值但强制压缩
        context = CompactionContext(
            messages=[{"role": "user", "content": "Test"}],
            current_tokens=1000,
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test"
        )
        
        result = await manager.check_and_compact(context, force=True)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_metrics_recording(self, manager, strategy, context):
        """测试：记录压缩指标"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        # 执行压缩
        await manager.check_and_compact(context)
        
        # 检查指标
        metrics = manager.get_metrics("opencode")
        
        assert metrics.success_count > 0
        assert metrics.total_tokens_saved > 0
        assert metrics.last_compaction_time is not None
        assert metrics.success_rate == 1.0
    
    @pytest.mark.asyncio
    async def test_metrics_success_rate(self, manager, strategy):
        """测试：成功率计算"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        # 执行多次压缩
        for i in range(5):
            context = CompactionContext(
                messages=[{"role": "user", "content": f"Test {i}"}],
                current_tokens=100000,
                max_tokens=128000,
                model_name="gpt-4",
                session_id=f"test-{i}"
            )
            await manager.check_and_compact(context)
        
        metrics = manager.get_metrics()
        
        assert metrics.success_count == 5
        assert metrics.success_rate == 1.0
        assert metrics.avg_duration > 0
    
    def test_list_strategies(self, manager, strategy):
        """测试：列出所有策略"""
        manager.register_strategy("opencode", strategy)
        
        strategies = manager.list_strategies()
        
        assert len(strategies) == 1
        assert strategies[0].name == "opencode"
    
    def test_get_current_strategy_name(self, manager, strategy):
        """测试：获取当前策略名称"""
        manager.register_strategy("opencode", strategy)
        manager.set_strategy("opencode")
        
        name = manager.get_current_strategy_name()
        
        assert name == "opencode"
    
    def test_get_current_strategy_name_when_none(self, manager):
        """测试：未设置策略时返回 None"""
        name = manager.get_current_strategy_name()
        
        assert name is None
    
    def test_manager_with_config(self):
        """测试：带配置的管理器"""
        config = {
            "opencode": {
                "prune_minimum": 10000,
                "auto_threshold": 0.8
            }
        }
        
        manager = CompactionManager(config)
        
        assert manager.config == config
    
    @pytest.mark.asyncio
    async def test_multiple_strategies(self, manager):
        """测试：注册多个策略"""
        strategy1 = OpenCodeStrategy({"auto_threshold": 0.7})
        strategy2 = OpenCodeStrategy({"auto_threshold": 0.8})
        
        manager.register_strategy("strategy1", strategy1)
        manager.register_strategy("strategy2", strategy2)
        
        assert len(manager.strategies) == 2
        
        # 切换策略
        manager.set_strategy("strategy1")
        assert manager.current_strategy == "strategy1"
        
        manager.set_strategy("strategy2")
        assert manager.current_strategy == "strategy2"


class TestCompactionMetrics:
    """CompactionMetrics 测试"""
    
    def test_success_rate_with_no_attempts(self):
        """测试：无尝试时成功率为0"""
        from core.compaction.manager import CompactionMetrics
        
        metrics = CompactionMetrics(strategy_name="test")
        
        assert metrics.success_rate == 0.0
    
    def test_success_rate_calculation(self):
        """测试：成功率计算"""
        from core.compaction.manager import CompactionMetrics
        
        metrics = CompactionMetrics(strategy_name="test")
        metrics.success_count = 8
        metrics.failure_count = 2
        
        assert metrics.success_rate == 0.8
    
    def test_avg_duration_with_no_success(self):
        """测试：无成功时平均耗时为0"""
        from core.compaction.manager import CompactionMetrics
        
        metrics = CompactionMetrics(strategy_name="test")
        
        assert metrics.avg_duration == 0.0
    
    def test_avg_duration_calculation(self):
        """测试：平均耗时计算"""
        from core.compaction.manager import CompactionMetrics
        
        metrics = CompactionMetrics(strategy_name="test")
        metrics.success_count = 4
        metrics.total_duration = 10.0
        
        assert metrics.avg_duration == 2.5

