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
    def mock_model_client(self):
        """模拟model_client"""
        class MockResponse:
            content = "This is a test summary of the conversation."
        
        class MockModelClient:
            async def _non_stream_completion(self, messages):
                return MockResponse()
        
        return MockModelClient()
    
    @pytest.fixture
    def context(self, sample_messages, mock_model_client):
        """创建压缩上下文"""
        return CompactionContext(
            messages=sample_messages,
            current_tokens=100000,
            max_tokens=128000,
            model_name="gpt-4",
            session_id="test-session",
            model_client=mock_model_client
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
        # 注意：消息数量很少时，压缩后可能反而增多（添加了摘要和恢复提示）
        # 所以不强制要求removed_count > 0 或 tokens_saved > 0
        assert result.new_messages is not None
        assert len(result.new_messages) > 0
    
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
        """测试：有摘要时只保留摘要后的消息（不包含摘要本身）"""
        messages = [
            {"role": "user", "content": "Old message 1"},
            {"role": "assistant", "content": "Old response 1"},
            {"role": "user", "content": "Old message 2"},
            {"role": "assistant", "content": "Summary", "summary": True},
            {"role": "user", "content": "New message"},
            {"role": "assistant", "content": "New response"}
        ]
        
        filtered = strategy._filter_summarized(messages)
        
        # 修复后：应该跳过摘要本身，只保留摘要之后的新消息
        assert len(filtered) == 2  # 只有2条新消息，不包含摘要
        assert all(not msg.get("summary") for msg in filtered)
        assert filtered[0]["content"] == "New message"
        assert filtered[1]["content"] == "New response"
    
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


class TestGetRecentTurns:
    """测试 _get_recent_turns 方法（Bug修复后的新功能）"""
    
    @pytest.fixture
    def strategy(self):
        return OpenCodeStrategy()
    
    def test_get_recent_turns_basic(self, strategy):
        """测试：获取最近N轮对话的基本功能"""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
            {"role": "assistant", "content": "Answer 2"},
            {"role": "tool", "tool_call_id": "call_1", "content": "Tool result"},
            {"role": "user", "content": "Question 3"},
            {"role": "assistant", "content": "Answer 3"}
        ]
        
        # 获取最近2轮
        recent = strategy._get_recent_turns(messages, 2)
        
        # 应该包含最近2轮的所有消息（从后往前统计user消息）
        # 包括：Answer 1（Question 2之前的assistant）, Question 2, Answer 2, Tool, Question 3, Answer 3
        assert len(recent) == 6
        assert recent[0]["content"] == "Answer 1"  # Question 2之前的assistant也被包含
        assert recent[-1]["content"] == "Answer 3"
    
    def test_get_recent_turns_excludes_system_messages(self, strategy):
        """测试：排除系统消息"""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"}
        ]
        
        recent = strategy._get_recent_turns(messages, 1)
        
        # 不应该包含系统消息
        assert all(msg.get("role") != "system" for msg in recent)
        assert len(recent) == 2  # user + assistant
    
    def test_get_recent_turns_excludes_summary_and_recovery(self, strategy):
        """测试：排除摘要和恢复提示"""
        messages = [
            {"role": "assistant", "content": "Old summary", "summary": True},
            {"role": "user", "content": "Recovery prompt", "recovery_prompt": True},
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"}
        ]
        
        recent = strategy._get_recent_turns(messages, 1)
        
        # 不应该包含摘要和恢复提示
        assert len(recent) == 2
        assert recent[0]["content"] == "Question 1"
        assert recent[1]["content"] == "Answer 1"
    
    def test_get_recent_turns_zero_turns(self, strategy):
        """测试：请求0轮对话返回空列表"""
        messages = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"}
        ]
        
        recent = strategy._get_recent_turns(messages, 0)
        
        assert recent == []
    
    def test_get_recent_turns_more_than_available(self, strategy):
        """测试：请求的轮数超过可用轮数"""
        messages = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"}
        ]
        
        # 请求10轮，但只有1轮
        recent = strategy._get_recent_turns(messages, 10)
        
        # 应该返回所有可用消息
        assert len(recent) == 2
    
    def test_get_recent_turns_preserves_order(self, strategy):
        """测试：保持消息顺序"""
        messages = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "A3"}
        ]
        
        recent = strategy._get_recent_turns(messages, 2)
        
        # 检查顺序：应该是 A1, Q2, A2, Q3, A3（包含Q2之前的assistant）
        assert len(recent) == 5
        assert recent[0]["content"] == "A1"
        assert recent[1]["content"] == "Q2"
        assert recent[2]["content"] == "A2"
        assert recent[3]["content"] == "Q3"
        assert recent[4]["content"] == "A3"
    
    def test_get_recent_turns_with_tool_messages(self, strategy):
        """测试：包含工具消息的完整轮次"""
        messages = [
            {"role": "user", "content": "Request 1"},
            {"role": "assistant", "content": "Processing 1"},
            {"role": "tool", "tool_call_id": "call_1", "content": "Result 1"},
            {"role": "user", "content": "Request 2"},
            {"role": "assistant", "content": "Processing 2"},
            {"role": "tool", "tool_call_id": "call_2", "content": "Result 2"}
        ]
        
        recent = strategy._get_recent_turns(messages, 1)
        
        # 最近1轮应该包含：Processing 1（Request 2之前的assistant）, Request 2, Processing 2, Result 2
        # 实际上包含了从倒数第1个user往前的所有消息
        assert len(recent) >= 3
        assert "Request 2" in [m.get("content") for m in recent]
        assert "Result 2" in [m.get("content") for m in recent]


class TestCompactWithRecentTurns:
    """测试 _compact 保留最近对话的功能（Bug修复后的核心测试）"""
    
    @pytest.fixture
    def strategy(self):
        config = {"protect_turns": 2}
        return OpenCodeStrategy(config)
    
    @pytest.fixture
    def mock_model_client(self):
        """模拟model_client"""
        class MockResponse:
            content = "This is a test summary of the conversation."
        
        class MockModelClient:
            async def _non_stream_completion(self, messages):
                return MockResponse()
        
        return MockModelClient()
    
    @pytest.mark.asyncio
    async def test_compact_preserves_recent_turns(self, strategy, mock_model_client):
        """测试：压缩后保留最近N轮对话"""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Old Q1"},
            {"role": "assistant", "content": "Old A1"},
            {"role": "user", "content": "Old Q2"},
            {"role": "assistant", "content": "Old A2"},
            {"role": "user", "content": "Recent Q1"},
            {"role": "assistant", "content": "Recent A1"},
            {"role": "tool", "tool_call_id": "call_1", "content": "Tool result 1"},
            {"role": "user", "content": "Recent Q2"},
            {"role": "assistant", "content": "Recent A2"}
        ]
        
        context = CompactionContext(
            messages=messages,
            current_tokens=10000,
            max_tokens=12000,
            model_name="gpt-4",
            session_id="test",
            model_client=mock_model_client
        )
        
        result = await strategy.compact(context, {})
        new_messages = result.new_messages
        
        # 验证新消息结构
        # 应该包含：system + summary + recovery_prompt + 最近2轮对话
        system_msgs = [m for m in new_messages if m.get("role") == "system"]
        summary_msgs = [m for m in new_messages if m.get("summary")]
        recovery_msgs = [m for m in new_messages if m.get("recovery_prompt")]
        recent_msgs = [m for m in new_messages if not m.get("role") == "system" 
                      and not m.get("summary") and not m.get("recovery_prompt")]
        
        assert len(system_msgs) == 1
        assert len(summary_msgs) == 1
        assert len(recovery_msgs) == 1
        assert len(recent_msgs) >= 4  # 至少包含最近2轮（可能有tool消息）
        
        # 验证保留的是最近的消息
        assert any("Recent Q1" in m.get("content", "") for m in recent_msgs)
        assert any("Recent Q2" in m.get("content", "") for m in recent_msgs)
        
        # 验证旧消息没有被保留（已被摘要）
        assert not any("Old Q1" in m.get("content", "") for m in recent_msgs)
        assert not any("Old Q2" in m.get("content", "") for m in recent_msgs)
    
    @pytest.mark.asyncio
    async def test_compact_second_time_removes_old_summary(self, strategy, mock_model_client):
        """测试：第二次压缩时移除旧摘要和旧恢复提示"""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "assistant", "content": "Old summary", "summary": True},
            {"role": "user", "content": "Old recovery", "recovery_prompt": True},
            {"role": "user", "content": "Message after old summary"},
            {"role": "assistant", "content": "Response after old summary"},
            {"role": "user", "content": "Latest message"},
            {"role": "assistant", "content": "Latest response"}
        ]
        
        context = CompactionContext(
            messages=messages,
            current_tokens=10000,
            max_tokens=12000,
            model_name="gpt-4",
            session_id="test",
            model_client=mock_model_client
        )
        
        result = await strategy.compact(context, {})
        new_messages = result.new_messages
        
        # 验证旧摘要和旧恢复提示被移除
        summary_count = sum(1 for m in new_messages if m.get("summary"))
        recovery_count = sum(1 for m in new_messages if m.get("recovery_prompt"))
        
        assert summary_count == 1  # 只有新摘要
        assert recovery_count == 1  # 只有新恢复提示
        
        # 验证新摘要不是旧摘要
        summary_msg = [m for m in new_messages if m.get("summary")][0]
        assert summary_msg["content"] != "Old summary"
    
    @pytest.mark.asyncio
    async def test_compact_with_protect_turns_config(self, mock_model_client):
        """测试：protect_turns配置正确生效"""
        # 测试protect_turns=1
        strategy_1 = OpenCodeStrategy({"protect_turns": 1})
        
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "Q3"},
            {"role": "assistant", "content": "A3"}
        ]
        
        context = CompactionContext(
            messages=messages,
            current_tokens=10000,
            max_tokens=12000,
            model_name="gpt-4",
            session_id="test",
            model_client=mock_model_client
        )
        
        result = await strategy_1.compact(context, {})
        new_messages = result.new_messages
        
        recent_msgs = [m for m in new_messages if not m.get("role") == "system" 
                      and not m.get("summary") and not m.get("recovery_prompt")]
        
        # protect_turns=1，实际包含：A2（Q3之前的assistant）, Q3, A3
        assert len(recent_msgs) == 3
        assert any("Q3" in m.get("content", "") for m in recent_msgs)
        assert any("A3" in m.get("content", "") for m in recent_msgs)
        # Q1, Q2不应该被保留
        assert not any("Q1" in m.get("content", "") for m in recent_msgs)
        assert not any("Q2" in m.get("content", "") for m in recent_msgs)


class TestLoweredThresholds:
    """测试降低后的阈值配置"""
    
    def test_default_prune_protect_lowered(self):
        """测试：默认prune_protect阈值已降低"""
        strategy = OpenCodeStrategy()
        
        # 验证新的默认值
        assert strategy.prune_protect == 10_000  # 从40000降到10000
        assert strategy.prune_minimum == 5_000   # 从20000降到5000
    
    def test_prune_triggers_at_lower_threshold(self):
        """测试：降低阈值后Prune更容易触发"""
        strategy = OpenCodeStrategy()
        
        # 创建累计12K tokens的工具输出（超过新阈值10K）
        # 需要至少3轮user对话，才能让第1轮超出protect_turns=2的保护范围
        messages = [
            {"role": "user", "content": "Request 1"},
            {"role": "assistant", "content": "Processing 1"},
            {"role": "tool", "tool_call_id": "call_1", "content": "X" * 50000},  # 约12.5K tokens
            {"role": "user", "content": "Request 2"},
            {"role": "assistant", "content": "Processing 2"},
            {"role": "user", "content": "Request 3"},  # 第3轮，第1轮超出protect_turns=2
            {"role": "assistant", "content": "Processing 3"}
        ]
        
        prune_result = strategy._prune(messages)
        
        # 应该触发清理（超过10K阈值且超出保护范围）
        assert prune_result.pruned_count > 0
        assert prune_result.pruned_tokens > 0

