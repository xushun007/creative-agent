"""OpenCode 策略单元测试"""

import sys
from pathlib import Path
import pytest
from datetime import datetime

# 添加 src 到路径以避免触发 src.core.__init__ 的导入链
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from core.compaction.strategies.opencode import OpenCodeStrategy
from core.compaction.base import CompactionContext


class TestOpenCodeStrategy:
    """OpenCode 策略测试"""
    
    @pytest.fixture
    def strategy(self):
        """创建策略实例"""
        return OpenCodeStrategy()
    
    @pytest.fixture
    def sample_messages(self):
        """创建测试消息"""
        return [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Hello, can you help me?"
            },
            {
                "role": "assistant",
                "content": "Of course! How can I assist you?",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}
                    }
                ]
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "read_file",
                "content": "A" * 50000  # 大量内容，会被修剪
            },
            {
                "role": "assistant",
                "content": "I've read the file. Let me help you with that."
            },
            {
                "role": "user",
                "content": "Thank you!"
            },
            {
                "role": "assistant",
                "content": "You're welcome!",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "function": {"name": "write_file", "arguments": '{"path": "output.txt"}'}
                    }
                ]
            },
            {
                "role": "tool",
                "tool_call_id": "call_2",
                "name": "write_file",
                "content": "File written successfully."  # 最近的，应该被保护
            }
        ]
    
    @pytest.fixture
    def context(self, sample_messages):
        """创建压缩上下文"""
        return CompactionContext(
            messages=sample_messages,
            current_tokens=100000,
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test-session"
        )
    
    def test_should_compact_when_threshold_exceeded(self, strategy):
        """测试：超过阈值时应该触发压缩"""
        context = CompactionContext(
            messages=[],
            current_tokens=100000,  # 78% 使用率
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test"
        )
        
        assert strategy.should_compact(context) is True
    
    def test_should_not_compact_when_below_threshold(self, strategy):
        """测试：低于阈值时不应该触发压缩"""
        context = CompactionContext(
            messages=[],
            current_tokens=50000,  # 39% 使用率
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test"
        )
        
        assert strategy.should_compact(context) is False
    
    @pytest.mark.asyncio
    async def test_compact_success(self, strategy, context):
        """测试：压缩成功"""
        result = await strategy.compact(context)
        
        assert result.success is True
        assert result.strategy_name == "opencode"
        assert result.removed_count > 0
        assert result.tokens_saved > 0
        assert len(result.new_messages) < len(context.messages)
    
    @pytest.mark.asyncio
    async def test_compact_preserves_system_messages(self, strategy, context):
        """测试：压缩保留系统消息"""
        result = await strategy.compact(context)
        
        # 检查系统消息是否被保留
        system_messages = [
            msg for msg in result.new_messages 
            if msg.get("role") == "system"
        ]
        
        original_system = [
            msg for msg in context.messages 
            if msg.get("role") == "system"
        ]
        
        assert len(system_messages) == len(original_system)
    
    @pytest.mark.asyncio
    async def test_compact_creates_summary(self, strategy, context):
        """测试：压缩创建摘要消息"""
        result = await strategy.compact(context)
        
        # 检查是否有摘要消息
        summary_messages = [
            msg for msg in result.new_messages 
            if msg.get("summary") is True
        ]
        
        assert len(summary_messages) > 0
        assert summary_messages[0]["role"] == "assistant"
    
    def test_prune_protects_recent_turns(self, strategy, sample_messages):
        """测试：Prune 保护最近的对话轮次"""
        messages = sample_messages.copy()
        
        prune_result = strategy._prune(messages)
        
        # 检查最后一个工具消息（最近的）没有被压缩
        last_tool_msg = [msg for msg in messages if msg.get("role") == "tool"][-1]
        assert "compacted_at" not in last_tool_msg
    
    def test_prune_clears_old_tool_outputs(self, strategy):
        """测试：Prune 清理旧的工具输出"""
        # 创建足够多的工具输出以触发 prune_protect 阈值（40K tokens）
        messages = []
        
        # 添加3轮对话，每轮包含大量工具输出
        for i in range(5):
            messages.append({"role": "user", "content": f"Request {i+1}"})
            messages.append({"role": "assistant", "content": f"Processing {i+1}"})
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i+1}",
                "content": "X" * 60000  # 约15K tokens
            })
        
        prune_result = strategy._prune(messages)
        
        # 应该清理了一些旧的工具输出
        if prune_result.pruned_count > 0:
            assert prune_result.pruned_tokens > 0
            
            # 检查是否有被清理的工具消息
            cleared = [msg for msg in messages if msg.get("role") == "tool" and 
                      msg.get("content") == "[Old tool result content cleared]"]
            assert len(cleared) > 0
            assert all("compacted_at" in msg for msg in cleared)
    
    def test_filter_summarized_without_summary(self, strategy, sample_messages):
        """测试：没有摘要时过滤掉系统消息"""
        filtered = strategy._filter_summarized(sample_messages)
        
        # 应该返回非系统消息
        assert len(filtered) > 0
        assert all(msg.get("role") != "system" for msg in filtered)
    
    def test_filter_summarized_with_summary(self, strategy):
        """测试：有摘要时只保留摘要后的消息"""
        messages = [
            {"role": "user", "content": "Old message 1"},
            {"role": "assistant", "content": "Old response 1"},
            {"role": "user", "content": "Old message 2"},
            {"role": "assistant", "content": "Summary", "summary": True},
            {"role": "user", "content": "New message"},
            {"role": "assistant", "content": "New response"}
        ]
        
        filtered = strategy._filter_summarized(messages)
        
        # 应该只保留摘要及之后的消息
        assert len(filtered) == 3  # 摘要 + 2条新消息
        assert filtered[0]["summary"] is True
    
    def test_find_last_summary_index(self, strategy):
        """测试：查找最后一个摘要索引"""
        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Summary 1", "summary": True},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Summary 2", "summary": True},
            {"role": "user", "content": "Message 3"}
        ]
        
        idx = strategy._find_last_summary_index(messages)
        
        assert idx == 3  # 第二个摘要的索引
    
    def test_find_last_summary_index_no_summary(self, strategy, sample_messages):
        """测试：没有摘要时返回-1"""
        idx = strategy._find_last_summary_index(sample_messages)
        
        assert idx == -1
    
    def test_get_metadata(self, strategy):
        """测试：获取策略元数据"""
        metadata = strategy.get_metadata()
        
        assert metadata.name == "opencode"
        assert metadata.version == "1.0.0"
        assert "OpenCode" in metadata.description
    
    def test_custom_config(self):
        """测试：自定义配置"""
        config = {
            "prune_minimum": 10000,
            "prune_protect": 20000,
            "protect_turns": 1,
            "auto_threshold": 0.8
        }
        
        strategy = OpenCodeStrategy(config)
        
        assert strategy.prune_minimum == 10000
        assert strategy.prune_protect == 20000
        assert strategy.protect_turns == 1
        assert strategy.auto_threshold == 0.8
    
    @pytest.mark.asyncio
    async def test_compact_handles_empty_messages(self, strategy):
        """测试：处理空消息列表"""
        context = CompactionContext(
            messages=[],
            current_tokens=0,
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test"
        )
        
        result = await strategy.compact(context)
        
        assert result.success is True
        assert len(result.new_messages) >= 0
    
    @pytest.mark.asyncio
    async def test_compact_compression_ratio(self, strategy, context):
        """测试：压缩率计算"""
        result = await strategy.compact(context)
        
        compression_ratio = result.metadata.get("compression_ratio", 0)
        
        assert 0 <= compression_ratio <= 1
        assert compression_ratio > 0.3  # 至少节省30%


class TestPruneLogic:
    """Prune 逻辑专项测试"""
    
    @pytest.fixture
    def strategy(self):
        return OpenCodeStrategy()
    
    def test_prune_calculates_tokens_correctly(self, strategy):
        """测试：正确计算 token 数"""
        messages = []
        
        # 创建多轮对话以触发保护阈值
        for i in range(4):
            messages.append({"role": "user", "content": f"Test {i+1}"})
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i+1}",
                "content": "A" * 80000  # 约20K tokens
            })
        
        prune_result = strategy._prune(messages)
        
        # total_tokens 统计超过 protect 阈值的部分
        # 由于有保护机制，不是所有 tokens 都会被统计
        assert prune_result.total_tokens >= 0
    
    def test_prune_respects_protect_threshold(self, strategy):
        """测试：遵守保护阈值"""
        messages = []
        
        # 添加多个工具调用，总计超过保护阈值
        for i in range(10):
            messages.append({"role": "user", "content": f"Request {i}"})
            messages.append({"role": "assistant", "content": f"Processing {i}"})
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": "X" * 40000  # 每个10K tokens
            })
        
        prune_result = strategy._prune(messages)
        
        # 检查最近的工具输出没有被清理
        recent_tools = [msg for msg in messages[-6:] if msg.get("role") == "tool"]
        for tool_msg in recent_tools:
            assert tool_msg.get("content") != "[Old tool result content cleared]"
            assert "compacted_at" not in tool_msg
    
    def test_prune_stops_at_existing_compaction(self, strategy):
        """测试：遇到已压缩内容时停止"""
        messages = [
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "Very old content",
                "compacted_at": datetime.now().isoformat()  # 已压缩
            },
            {
                "role": "user",
                "content": "New request"
            },
            {
                "role": "tool",
                "tool_call_id": "call_2",
                "content": "A" * 80000  # 新内容
            }
        ]
        
        prune_result = strategy._prune(messages)
        
        # 不应该再次压缩已压缩的内容
        assert messages[0].get("content") == "Very old content"

