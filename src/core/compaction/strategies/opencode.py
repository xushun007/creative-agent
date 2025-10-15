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
    
    PRUNE_MINIMUM = 20_000
    PRUNE_PROTECT = 40_000
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
        if should:
            logger.info(f"触发压缩: {context.current_tokens}/{context.max_tokens} ({usage_ratio:.1%})")
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
        
        # 保留系统消息
        for msg in messages:
            if is_system_message(msg):
                new_messages.append(msg)
        
        # 添加摘要
        new_messages.append({
            "role": "assistant",
            "content": summary_text,
            "summary": True,
            "timestamp": datetime.now().isoformat()
        })
        
        # 添加恢复提示
        new_messages.append({
            "role": "user",
            "content": "Use the above summary to continue our conversation from where we left off.",
            "timestamp": datetime.now().isoformat()
        })
        
        # 添加摘要后的新消息
        summary_idx = self._find_last_summary_index(messages)
        if summary_idx != -1 and summary_idx < len(messages) - 1:
            new_messages.extend(messages[summary_idx + 1:])
        
        return new_messages
    
    def _filter_summarized(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤已摘要的消息"""
        last_summary_idx = self._find_last_summary_index(messages)
        if last_summary_idx == -1:
            return [msg for msg in messages if not is_system_message(msg)]
        return messages[last_summary_idx:]
    
    def _find_last_summary_index(self, messages: List[Dict[str, Any]]) -> int:
        """查找最后一个摘要索引"""
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant" and messages[i].get("summary"):
                return i
        return -1
    
    async def _generate_summary(self, messages: List[Dict[str, Any]], context: CompactionContext) -> str:
        """生成对话摘要（TODO: 调用LLM）"""
        user_turns = count_user_turns(messages)
        total_messages = len(messages)
        
        summary = f"""# Previous Conversation Summary

This conversation had {user_turns} user interactions with {total_messages} total messages.

## Key Points:
- The conversation covered multiple topics
- Various tools were used to assist with tasks
- Progress was made on the discussed objectives

## Context:
Please continue based on the above summary and any new messages that follow."""
        
        logger.info(f"生成摘要: {user_turns} 轮对话, {total_messages} 条消息")
        return summary.strip()
    
    def get_metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="opencode",
            version="1.0.0",
            description="OpenCode双层压缩策略：Prune清理工具输出 + Compact生成摘要"
        )
