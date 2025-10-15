"""消息压缩使用示例"""

import asyncio
from datetime import datetime

from src.core.compaction import (
    CompactionManager,
    OpenCodeStrategy,
    CompactionContext,
)


def create_sample_messages():
    """创建示例消息"""
    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant."
        },
        {
            "role": "user",
            "content": "Can you help me analyze this large file?"
        },
        {
            "role": "assistant",
            "content": "Of course! Let me read it.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "data.txt"}'
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "read_file",
            "content": "A" * 60000  # 大量内容，约 15K tokens
        },
        {
            "role": "assistant",
            "content": "I've read the file. It contains data that needs processing."
        },
        {
            "role": "user",
            "content": "Great! Can you process it?"
        },
        {
            "role": "assistant",
            "content": "Processing now...",
            "tool_calls": [
                {
                    "id": "call_2",
                    "function": {
                        "name": "process_data",
                        "arguments": '{"data": "..."}'
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": "call_2",
            "name": "process_data",
            "content": "B" * 50000  # 更多内容，约 12.5K tokens
        },
        {
            "role": "assistant",
            "content": "Processing complete! The results are ready."
        },
        {
            "role": "user",
            "content": "Perfect! Can you summarize the results?"
        },
        {
            "role": "assistant",
            "content": "Let me analyze and summarize...",
            "tool_calls": [
                {
                    "id": "call_3",
                    "function": {
                        "name": "analyze",
                        "arguments": '{}'
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": "call_3",
            "name": "analyze",
            "content": "Analysis results: The data shows interesting patterns..."
        }
    ]
    
    return messages


async def basic_example():
    """基础使用示例"""
    print("=" * 60)
    print("示例 1: 基础使用")
    print("=" * 60)
    
    # 1. 创建管理器和策略
    manager = CompactionManager()
    strategy = OpenCodeStrategy()
    
    # 2. 注册策略
    manager.register_strategy("opencode", strategy)
    manager.set_strategy("opencode")
    
    # 3. 创建测试消息
    messages = create_sample_messages()
    
    print(f"\n原始消息数: {len(messages)}")
    
    # 4. 创建压缩上下文
    context = CompactionContext(
        messages=messages,
        current_tokens=100000,  # 假设当前使用 100K tokens
        max_tokens=128000,      # 最大 128K tokens (78% 使用率)
        model_name="gpt-4",
        session_id="example-session-1"
    )
    
    # 5. 执行压缩
    print("\n开始压缩...")
    result = await manager.check_and_compact(context)
    
    if result:
        print(f"\n✅ 压缩成功!")
        print(f"   删除消息数: {result.removed_count}")
        print(f"   节省 tokens: {result.tokens_saved}")
        print(f"   压缩后消息数: {len(result.new_messages)}")
        print(f"   压缩率: {result.metadata.get('compression_ratio', 0):.1%}")
        
        # 显示压缩后的消息结构
        print("\n压缩后的消息类型:")
        for msg in result.new_messages:
            role = msg.get("role")
            is_summary = msg.get("summary", False)
            summary_tag = " [摘要]" if is_summary else ""
            print(f"   - {role}{summary_tag}")
    else:
        print("\n❌ 未触发压缩（可能未达到阈值）")


async def custom_config_example():
    """自定义配置示例"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义配置")
    print("=" * 60)
    
    # 自定义策略配置
    config = {
        "prune_minimum": 10000,   # 降低修剪阈值
        "prune_protect": 30000,   # 减少保护范围
        "protect_turns": 1,       # 只保护最近 1 轮
        "auto_threshold": 0.6     # 60% 就触发压缩
    }
    
    print(f"\n配置:")
    for key, value in config.items():
        print(f"   {key}: {value}")
    
    # 创建带配置的策略
    strategy = OpenCodeStrategy(config)
    
    manager = CompactionManager()
    manager.register_strategy("custom", strategy)
    manager.set_strategy("custom")
    
    # 创建较低使用率的上下文
    messages = create_sample_messages()
    context = CompactionContext(
        messages=messages,
        current_tokens=80000,   # 62.5% 使用率
        max_tokens=128000,
        model_name="gpt-4",
        session_id="example-session-2"
    )
    
    print(f"\n当前使用率: {context.current_tokens / context.max_tokens:.1%}")
    
    result = await manager.check_and_compact(context)
    
    if result:
        print(f"\n✅ 触发压缩（自定义阈值 60%）")
        print(f"   节省 tokens: {result.tokens_saved}")
    else:
        print("\n❌ 未触发压缩")


async def metrics_example():
    """监控指标示例"""
    print("\n" + "=" * 60)
    print("示例 3: 监控指标")
    print("=" * 60)
    
    manager = CompactionManager()
    strategy = OpenCodeStrategy()
    manager.register_strategy("opencode", strategy)
    manager.set_strategy("opencode")
    
    # 执行多次压缩
    print("\n执行 5 次压缩...")
    for i in range(5):
        messages = create_sample_messages()
        context = CompactionContext(
            messages=messages,
            current_tokens=100000 + i * 5000,
            max_tokens=128000,
            model_name="gpt-4",
            session_id=f"session-{i}"
        )
        
        result = await manager.check_and_compact(context)
        print(f"   第 {i+1} 次: {'成功' if result and result.success else '失败'}")
    
    # 获取指标
    metrics = manager.get_metrics()
    
    print("\n📊 压缩指标:")
    print(f"   策略: {metrics.strategy_name}")
    print(f"   成功次数: {metrics.success_count}")
    print(f"   失败次数: {metrics.failure_count}")
    print(f"   成功率: {metrics.success_rate:.1%}")
    print(f"   总节省 tokens: {metrics.total_tokens_saved:,}")
    print(f"   平均耗时: {metrics.avg_duration:.3f}s")


async def force_compact_example():
    """强制压缩示例"""
    print("\n" + "=" * 60)
    print("示例 4: 强制压缩")
    print("=" * 60)
    
    manager = CompactionManager()
    strategy = OpenCodeStrategy()
    manager.register_strategy("opencode", strategy)
    manager.set_strategy("opencode")
    
    # 创建低使用率的上下文
    messages = create_sample_messages()
    context = CompactionContext(
        messages=messages,
        current_tokens=30000,   # 只有 23% 使用率
        max_tokens=128000,
        model_name="gpt-4",
        session_id="force-example"
    )
    
    print(f"\n当前使用率: {context.current_tokens / context.max_tokens:.1%}")
    
    # 正常检查（不会触发）
    result = await manager.check_and_compact(context, force=False)
    print(f"正常检查: {'触发' if result else '未触发'}")
    
    # 强制压缩
    result = await manager.check_and_compact(context, force=True)
    print(f"强制压缩: {'成功' if result and result.success else '失败'}")
    
    if result:
        print(f"   节省 tokens: {result.tokens_saved}")


async def multiple_strategies_example():
    """多策略示例"""
    print("\n" + "=" * 60)
    print("示例 5: 多策略管理")
    print("=" * 60)
    
    manager = CompactionManager()
    
    # 注册多个策略
    aggressive_strategy = OpenCodeStrategy({"auto_threshold": 0.6})
    conservative_strategy = OpenCodeStrategy({"auto_threshold": 0.85})
    
    manager.register_strategy("aggressive", aggressive_strategy)
    manager.register_strategy("conservative", conservative_strategy)
    
    # 列出所有策略
    print("\n已注册的策略:")
    for metadata in manager.list_strategies():
        print(f"   - {metadata.name} v{metadata.version}")
        print(f"     {metadata.description}")
    
    # 测试不同策略
    messages = create_sample_messages()
    
    for strategy_name in ["aggressive", "conservative"]:
        print(f"\n使用策略: {strategy_name}")
        manager.set_strategy(strategy_name)
        
        context = CompactionContext(
            messages=messages,
            current_tokens=90000,   # 70% 使用率
            max_tokens=128000,
            model_name="gpt-4",
            session_id=f"{strategy_name}-session"
        )
        
        result = await manager.check_and_compact(context)
        print(f"   结果: {'触发压缩' if result else '未触发'}")


async def main():
    """运行所有示例"""
    print("\n" + "🚀 消息压缩功能示例".center(60, "="))
    print()
    
    try:
        await basic_example()
        await custom_config_example()
        await metrics_example()
        await force_compact_example()
        await multiple_strategies_example()
        
        print("\n" + "=" * 60)
        print("✅ 所有示例执行完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

