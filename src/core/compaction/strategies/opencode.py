"""OpenCode 压缩策略：Prune（清理工具输出）+ Compact（生成摘要）"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from ..base import CompactionStrategy, CompactionContext, CompactResult, StrategyMetadata
from ..utils import estimate_tokens, extract_message_text, is_system_message, count_user_turns

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass
class PruneResult:
    pruned_count: int
    pruned_tokens: int
    total_tokens: int


class OpenCodeStrategy(CompactionStrategy):
    """OpenCode 双层压缩策略"""
    
    PRUNE_MINIMUM = 5_000
    PRUNE_PROTECT = 10_000
    PROTECT_TURNS = 2
    AUTO_COMPACT_THRESHOLD = 0.75
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.prune_minimum = self.config.get("prune_minimum", self.PRUNE_MINIMUM)
        self.prune_protect = self.config.get("prune_protect", self.PRUNE_PROTECT)
        self.protect_turns = self.config.get("protect_turns", self.PROTECT_TURNS)
        self.auto_threshold = self.config.get("auto_threshold", self.AUTO_COMPACT_THRESHOLD)
    
    def should_compact(self, context: CompactionContext) -> bool:
        if context.max_tokens == 0:
            return False
        usage_ratio = context.current_tokens / context.max_tokens
        should = usage_ratio >= self.auto_threshold
        compact_text = "触发压缩" if should else "不触发压缩"
        logger.info(f"压缩状态: {compact_text}, {context.current_tokens}/{context.max_tokens} ({usage_ratio:.1%})")
        return should
    
    async def compact(self, context: CompactionContext, config: Optional[Dict[str, Any]] = None) -> CompactResult:
        try:
            messages = context.messages.copy()
            initial_count = len(messages)
            initial_tokens = context.current_tokens
            
            # 1. Prune：清理旧工具输出
            prune_result = self._prune(messages)
            logger.info(f"Prune完成: 清理 {prune_result.pruned_count} 个工具输出, 节省 {prune_result.pruned_tokens} tokens")
            
            # 2. Compact：生成摘要
            compacted_messages = await self._compact(messages, context)
            
            # 3. 计算结果
            final_count = len(compacted_messages)
            final_tokens = sum(estimate_tokens(extract_message_text(msg)) for msg in compacted_messages)
            
            return CompactResult(
                success=True,
                new_messages=compacted_messages,
                removed_count=initial_count - final_count,
                tokens_saved=initial_tokens - final_tokens,
                strategy_name="opencode",
                metadata={
                    "prune_count": prune_result.pruned_count,
                    "compression_ratio": 1 - (final_tokens / initial_tokens) if initial_tokens > 0 else 0
                }
            )
        except Exception as e:
            logger.error(f"压缩失败: {e}")
            return CompactResult(
                success=False,
                new_messages=context.messages,
                removed_count=0,
                tokens_saved=0,
                strategy_name="opencode",
                error=str(e)
            )
    
    def _prune(self, messages: List[Dict[str, Any]]) -> PruneResult:
        """修剪旧工具输出"""
        total_tokens = 0
        pruned_tokens = 0
        pruned_count = 0
        turn_count = 0
        
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            role = msg.get("role", "")
            
            if role == "user" and not is_system_message(msg):
                turn_count += 1
            
            if turn_count < self.protect_turns:
                continue
            
            if role == "assistant" and msg.get("summary"):
                break
            
            if role == "tool":
                if msg.get("compacted_at"):
                    break
                
                content = msg.get("content", "")
                tokens = estimate_tokens(content)
                total_tokens += tokens
                
                if total_tokens > self.prune_protect:
                    msg["content"] = "[Old tool result content cleared]"
                    msg["compacted_at"] = datetime.now().isoformat()
                    pruned_tokens += tokens
                    pruned_count += 1
        
        return PruneResult(pruned_count, pruned_tokens, total_tokens)
    
    async def _compact(self, messages: List[Dict[str, Any]], context: CompactionContext) -> List[Dict[str, Any]]:
        """生成摘要并替换旧消息"""
        to_summarize = self._filter_summarized(messages)
        
        if not to_summarize:
            return messages
        
        summary_text = await self._generate_summary(to_summarize, context)
        
        new_messages = []
        
        # 1. 保留系统消息
        for msg in messages:
            if is_system_message(msg):
                new_messages.append(msg)
        
        # 2. 添加摘要
        new_messages.append({
            "role": "assistant",
            "content": summary_text,
            "summary": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # 3. 添加恢复提示
        new_messages.append({
            "role": "user",
            "content": "Use the above summary to continue our conversation from where we left off.",
            "timestamp": datetime.now().isoformat(),
            "recovery_prompt": True
        })
        
        # 4. 保留最近 N 轮对话（根据 protect_turns 配置）
        recent_messages = self._get_recent_turns(messages, self.protect_turns)
        new_messages.extend(recent_messages)
        
        logger.info(f"压缩完成: 保留 {len(recent_messages)} 条最近消息（{self.protect_turns}轮对话）")
        
        return new_messages
    
    def _get_recent_turns(self, messages: List[Dict[str, Any]], n_turns: int) -> List[Dict[str, Any]]:
        """获取最近 N 轮对话（user + assistant + tool 消息对）
        
        Args:
            messages: 所有消息列表
            n_turns: 要保留的对话轮数
            
        Returns:
            最近 N 轮的消息列表
        """
        if n_turns <= 0:
            return []
        
        recent = []
        turn_count = 0
        
        # 从后向前遍历消息
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            role = msg.get("role", "")
            
            # 跳过系统消息、摘要和恢复提示
            if (is_system_message(msg) or 
                msg.get("summary") or 
                msg.get("recovery_prompt")):
                continue
            
            # 统计用户消息作为新一轮对话的标记
            if role == "user":
                turn_count += 1
                if turn_count > n_turns:
                    break
            
            # 插入到列表开头以保持原有顺序
            recent.insert(0, msg)
        
        return recent
    
    def _filter_summarized(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤已摘要的消息"""
        last_summary_idx = self._find_last_summary_index(messages)
        if last_summary_idx == -1:
            return [msg for msg in messages if not is_system_message(msg)]
        # 跳过旧摘要本身，只返回摘要之后的新消息
        return messages[last_summary_idx + 1:]
    
    def _find_last_summary_index(self, messages: List[Dict[str, Any]]) -> int:
        """查找最后一个摘要索引"""
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant" and messages[i].get("summary"):
                return i
        return -1
    
    async def _generate_summary(self, messages: List[Dict[str, Any]], context: CompactionContext) -> str:
        """生成对话摘要（调用 LLM）"""
        
        if not context.model_client:
            raise ValueError("未提供 model_client，无法生成摘要")
        
        # 构建摘要请求消息
        summary_messages = [
            {"role": "system","content": "你是一个专业的对话摘要助手，擅长提取关键信息并生成简洁的摘要。"},
            {"role": "user", "content": self._build_summary_prompt(messages)}
        ]
        
        # 直接调用底层方法，不修改 conversation_history（避免并发问题）
        response = await context.model_client._non_stream_completion(summary_messages)
        summary = response.content
        
        if not summary or len(summary.strip()) < 10:
            raise ValueError(f"LLM 返回的摘要过短: {len(summary.strip())} 字符")
        
        logger.info(f"生成摘要成功: {len(messages)} 条消息 → {len(summary)} 字符")
        return summary.strip()
    
    def _build_summary_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """构建摘要提示词（与 OpenCode 一致：不截断内容）"""
        # OpenCode 的做法：完整传递所有消息，不做截断
        # 对话范围已由 _filter_summarized 控制（只取最后一个摘要之后的消息）
        conversation_lines = []
        for msg in messages:
            if is_system_message(msg):
                continue
            
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            conversation_lines.append(f"[{role}]: {content}")
        
        conversation_text = "\n".join(conversation_lines)
        
        # 使用与 OpenCode 相同的提示词
        return f"""Provide a detailed but concise summary of our conversation above.

Focus on information that would be helpful for continuing the conversation, including:
- What we did
- What we're doing
- Which files we're working on
- What we're going to do next

Conversation:
{conversation_text}

Please provide the summary in Chinese:"""
    
    def get_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="opencode",
            version="1.0.0",
            description="OpenCode双层压缩策略：Prune清理工具输出 + Compact生成摘要"
        )
