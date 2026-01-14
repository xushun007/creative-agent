"""Hook provider and multi-processor dispatcher."""

from __future__ import annotations

import threading
from typing import Iterable, Optional

from utils.logger import logger

from .interfaces import HookEvent, HookProcessor
from .processors import LoggerHookProcessor


class SynchronousMultiHookProcessor(HookProcessor):
    """Forwards hook events to registered processors."""

    def __init__(self) -> None:
        self._processors: tuple[HookProcessor, ...] = ()
        self._lock = threading.Lock()

    def add_processor(self, processor: HookProcessor) -> None:
        with self._lock:
            self._processors += (processor,)

    def set_processors(self, processors: Iterable[HookProcessor]) -> None:
        with self._lock:
            self._processors = tuple(processors)

    def on_event(self, event: HookEvent) -> None:
        for processor in self._processors:
            try:
                processor.on_event(event)
            except Exception as exc:
                logger.error(f"Hook processor {processor} failed on_event: {exc}")

    def shutdown(self) -> None:
        for processor in self._processors:
            try:
                processor.shutdown()
            except Exception as exc:
                logger.error(f"Hook processor {processor} failed shutdown: {exc}")

    def force_flush(self) -> None:
        for processor in self._processors:
            try:
                processor.force_flush()
            except Exception as exc:
                logger.error(f"Hook processor {processor} failed force_flush: {exc}")


class HookProvider:
    """Manages hook processors and emits events."""

    def __init__(self, disabled: bool = False, with_default_processors: bool = True) -> None:
        self._disabled = disabled
        self._multi_processor = SynchronousMultiHookProcessor()
        if with_default_processors:
            self._multi_processor.add_processor(LoggerHookProcessor())

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = disabled

    def register_processor(self, processor: HookProcessor) -> None:
        self._multi_processor.add_processor(processor)

    def set_processors(self, processors: Iterable[HookProcessor]) -> None:
        self._multi_processor.set_processors(processors)

    def emit(self, event: HookEvent) -> None:
        if self._disabled:
            return
        self._multi_processor.on_event(event)

    def emit_named(
        self,
        name: str,
        session_id: str,
        submission_id: Optional[str],
        payload: Optional[dict],
    ) -> None:
        event = HookEvent.create(name, session_id, submission_id, payload)
        self.emit(event)

    def shutdown(self) -> None:
        self._multi_processor.shutdown()

    def force_flush(self) -> None:
        self._multi_processor.force_flush()
