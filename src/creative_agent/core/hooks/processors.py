"""Built-in hook processors."""

from __future__ import annotations

import json
from typing import Any, Dict

from creative_agent.utils.logger import logger

from .context import HookContext
from .lifecycle import HooksBase


class LoggerHooks(HooksBase):
    """Logs hook events as JSON lines."""

    def __init__(self, include_payload: bool = True) -> None:
        self.include_payload = include_payload

    def _log(self, context: HookContext) -> None:
        data = {
            "name": context.name,
            "timestamp": context.timestamp,
            "session_id": context.session_id,
            "submission_id": context.submission_id,
            "payload": context.payload if self.include_payload else {},
        }
        try:
            text = json.dumps(data, ensure_ascii=False)
        except TypeError:
            data["payload"] = "<non-serializable payload>"
            text = json.dumps(data, ensure_ascii=False)
        logger.info(text)

    def on_session_start(self, context: HookContext) -> None:
        self._log(context)

    def on_session_stop(self, context: HookContext) -> None:
        self._log(context)

    def on_task_start(self, context: HookContext) -> None:
        self._log(context)

    def on_task_complete(self, context: HookContext) -> None:
        self._log(context)

    def on_turn_start(self, context: HookContext) -> None:
        self._log(context)

    def on_turn_complete(self, context: HookContext) -> None:
        self._log(context)

    def on_llm_start(self, context: HookContext) -> None:
        self._log(context)

    def on_llm_complete(self, context: HookContext) -> None:
        self._log(context)

    def on_tool_start(self, context: HookContext) -> None:
        self._log(context)

    def on_tool_complete(self, context: HookContext) -> None:
        self._log(context)

    def on_error(self, context: HookContext) -> None:
        self._log(context)
