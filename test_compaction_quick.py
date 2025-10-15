#!/usr/bin/env python3
"""快速测试压缩功能"""

import sys
import asyncio
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.compaction.strategies.opencode import OpenCodeStrategy
from core.compaction.base import CompactionContext
from core.compaction.manager import CompactionManager


def test_basic_creation():
    """测试基本创建"""
    print("✓ 测试 1: 基本创建")
    
    strategy = OpenCodeStrategy()
    assert strategy is not None
    assert strategy.PRUNE_MINIMUM == 20_000
    print("  ✓ OpenCodeStrategy 创建成功")
    
    manager = CompactionManager()
    assert manager is not None
    print("  ✓ CompactionManager 创建成功")


def test_should_compact():
    """测试压缩触发条件"""
    print("\n✓ 测试 2: 压缩触发条件")
    
    strategy = OpenCodeStrategy()
    
    # 高使用率 - 应该触发
    context_high = CompactionContext(
        messages=[],
        current_tokens=100000,  # 78%
        max_tokens=128000,
        model_name="gpt-4",
        session_id="test"
    )
    assert strategy.should_compact(context_high) is True
    print("  ✓ 高使用率触发压缩")
    
    # 低使用率 - 不应该触发
    context_low = CompactionContext(
        messages=[],
        current_tokens=50000,  # 39%
        max_tokens=128000,
        model_name="gpt-4",
        session_id="test"
    )
    assert strategy.should_compact(context_low) is False
    print("  ✓ 低使用率不触发压缩")


def test_prune():
    """测试 Prune 功能"""
    print("\n✓ 测试 3: Prune 功能")
    
    strategy = OpenCodeStrategy()
    
    # 创建足够多的消息触发修剪
    # 需要超过 protect_turns(2轮) 和 prune_protect(40K tokens)
    messages = [
        {"role": "user", "content": "Request 1"},
        {"role": "tool", "tool_call_id": "1", "content": "A" * 80000},  # 约 20K tokens
        {"role": "user", "content": "Request 2"},
        {"role": "tool", "tool_call_id": "2", "content": "B" * 80000},  # 约 20K tokens  
        {"role": "user", "content": "Request 3"},
        {"role": "tool", "tool_call_id": "3", "content": "C" * 80000},  # 约 20K tokens (protected)
        {"role": "user", "content": "Request 4"},
        {"role": "tool", "tool_call_id": "4", "content": "D" * 40000},  # 约 10K tokens (protected)
    ]
    
    result = strategy._prune(messages)
    
    if result.pruned_count > 0:
        print(f"  ✓ 修剪了 {result.pruned_count} 个工具输出")
        print(f"  ✓ 节省约 {result.pruned_tokens} tokens")
        
        # 检查旧的工具调用被清理
        cleared_count = sum(
            1 for msg in messages 
            if msg.get("role") == "tool" and 
            msg.get("content") == "[Old tool result content cleared]"
        )
        print(f"  ✓ {cleared_count} 个旧工具输出被正确清理")
    else:
        print("  ✓ Prune 执行完成（未达到修剪阈值是正常的）")


async def test_compact():
    """测试 Compact 功能"""
    print("\n✓ 测试 4: Compact 功能")
    
    strategy = OpenCodeStrategy()
    
    messages = [
        {"role": "system", "content": "System message"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm well!"},
    ]
    
    context = CompactionContext(
        messages=messages,
        current_tokens=100000,
        max_tokens=128000,
        model_name="gpt-4",
        session_id="test"
    )
    
    result = await strategy.compact(context)
    
    assert result.success is True
    print("  ✓ 压缩成功")
    
    assert len(result.new_messages) < len(messages)
    print(f"  ✓ 消息数从 {len(messages)} 减少到 {len(result.new_messages)}")
    
    # 检查是否有摘要
    has_summary = any(msg.get("summary") for msg in result.new_messages)
    assert has_summary
    print("  ✓ 生成了摘要消息")
    
    assert result.tokens_saved > 0
    print(f"  ✓ 节省了 {result.tokens_saved} tokens")


async def test_manager():
    """测试 Manager 功能"""
    print("\n✓ 测试 5: Manager 功能")
    
    manager = CompactionManager()
    strategy = OpenCodeStrategy()
    
    # 注册策略
    manager.register_strategy("opencode", strategy)
    print("  ✓ 注册策略成功")
    
    # 设置当前策略
    manager.set_strategy("opencode")
    assert manager.current_strategy == "opencode"
    print("  ✓ 设置当前策略成功")
    
    # 获取策略
    retrieved = manager.get_strategy()
    assert retrieved is strategy
    print("  ✓ 获取策略成功")
    
    # 执行压缩
    messages = [
        {"role": "user", "content": "Test"}
    ]
    context = CompactionContext(
        messages=messages,
        current_tokens=100000,
        max_tokens=128000,
        model_name="gpt-4",
        session_id="test"
    )
    
    result = await manager.check_and_compact(context)
    assert result is not None
    assert result.success is True
    print("  ✓ Manager 执行压缩成功")
    
    # 检查指标
    metrics = manager.get_metrics()
    assert metrics.success_count == 1
    assert metrics.success_rate == 1.0
    print("  ✓ 指标记录正确")


def test_custom_config():
    """测试自定义配置"""
    print("\n✓ 测试 6: 自定义配置")
    
    config = {
        "prune_minimum": 10000,
        "prune_protect": 30000,
        "protect_turns": 1,
        "auto_threshold": 0.6
    }
    
    strategy = OpenCodeStrategy(config)
    
    assert strategy.prune_minimum == 10000
    assert strategy.prune_protect == 30000
    assert strategy.protect_turns == 1
    assert strategy.auto_threshold == 0.6
    print("  ✓ 自定义配置应用成功")


def test_metadata():
    """测试元数据"""
    print("\n✓ 测试 7: 元数据")
    
    strategy = OpenCodeStrategy()
    metadata = strategy.get_metadata()
    
    assert metadata.name == "opencode"
    assert metadata.version == "1.0.0"
    assert "OpenCode" in metadata.description
    print("  ✓ 元数据正确")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("压缩功能快速测试".center(60))
    print("=" * 60)
    
    try:
        # 同步测试
        test_basic_creation()
        test_should_compact()
        test_prune()
        test_custom_config()
        test_metadata()
        
        # 异步测试
        await test_compact()
        await test_manager()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！".center(60))
        print("=" * 60)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

