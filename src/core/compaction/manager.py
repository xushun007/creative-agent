"""压缩管理器"""

import time
from typing import Dict, Optional, List
from dataclasses import dataclass

from .base import CompactionStrategy, CompactionContext, CompactResult, StrategyMetadata

try:
    from utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass
class CompactionMetrics:
    """压缩指标"""
    strategy_name: str
    success_count: int = 0
    failure_count: int = 0
    total_tokens_saved: int = 0
    total_duration: float = 0.0
    last_compaction_time: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    @property
    def avg_duration(self) -> float:
        return self.total_duration / self.success_count if self.success_count > 0 else 0.0


class CompactionManager:
    """压缩管理器：管理多个策略，选择和切换策略，执行压缩流程，记录指标"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.strategies: Dict[str, CompactionStrategy] = {}
        self.current_strategy: Optional[str] = None
        self.metrics: Dict[str, CompactionMetrics] = {}
    
    def register_strategy(self, name: str, strategy: CompactionStrategy) -> None:
        self.strategies[name] = strategy
        self.metrics[name] = CompactionMetrics(strategy_name=name)
        logger.info(f"注册压缩策略: {name}")
    
    def set_strategy(self, name: str) -> None:
        if name not in self.strategies:
            available = ", ".join(self.strategies.keys())
            raise ValueError(f"策略 '{name}' 不存在。可用策略: {available}")
        self.current_strategy = name
        logger.info(f"切换到压缩策略: {name}")
    
    def get_strategy(self, name: Optional[str] = None) -> CompactionStrategy:
        strategy_name = name or self.current_strategy
        if not strategy_name:
            raise ValueError("没有选择策略，请先调用 set_strategy()")
        if strategy_name not in self.strategies:
            raise ValueError(f"策略 '{strategy_name}' 不存在")
        return self.strategies[strategy_name]
    
    async def check_and_compact(self, context: CompactionContext, force: bool = False) -> Optional[CompactResult]:
        """检查并执行压缩"""
        strategy = self.get_strategy()
        
        if not force and not strategy.should_compact(context):
            logger.debug("当前不需要压缩")
            return None
        
        start_time = time.time()
        
        try:
            logger.info(f"开始执行压缩策略: {self.current_strategy}")
            result = await strategy.compact(context, self.config.get(self.current_strategy, {}))
            
            duration = time.time() - start_time
            self._record_compaction(self.current_strategy, result.success, result.tokens_saved, duration)
            
            if result.success:
                logger.info(f"压缩成功: 删除 {result.removed_count} 条消息, 节省 {result.tokens_saved} tokens, 耗时 {duration:.2f}s")
            else:
                logger.error(f"压缩失败: {result.error}")
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"压缩异常: {e}", exc_info=True)
            self._record_compaction(self.current_strategy, False, 0, duration)
            raise
    
    def _record_compaction(self, strategy_name: str, success: bool, tokens_saved: int, duration: float) -> None:
        if strategy_name not in self.metrics:
            self.metrics[strategy_name] = CompactionMetrics(strategy_name=strategy_name)
        
        metric = self.metrics[strategy_name]
        if success:
            metric.success_count += 1
            metric.total_tokens_saved += tokens_saved
        else:
            metric.failure_count += 1
        
        metric.total_duration += duration
        metric.last_compaction_time = time.time()
    
    def get_metrics(self, strategy_name: Optional[str] = None) -> CompactionMetrics:
        name = strategy_name or self.current_strategy
        if not name or name not in self.metrics:
            return CompactionMetrics(strategy_name=name or "unknown")
        return self.metrics[name]
    
    def list_strategies(self) -> List[StrategyMetadata]:
        return [strategy.get_metadata() for strategy in self.strategies.values()]
    
    def get_current_strategy_name(self) -> Optional[str]:
        return self.current_strategy
