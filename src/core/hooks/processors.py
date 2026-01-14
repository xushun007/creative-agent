"""Built-in hook processors."""

from __future__ import annotations

import json
from typing import Any

from utils.logger import logger

from .interfaces import HookEvent, HookProcessor


class LoggerHookProcessor(HookProcessor):
    """Logs hook events with minimal overhead."""

    def __init__(self, include_payload: bool = True) -> None:
        self.include_payload = include_payload

    def on_event(self, event: HookEvent) -> None:
        payload: Any = event.payload if self.include_payload else {}
        event_data = {
            "name": event.name,
            "timestamp": event.timestamp,
            "session_id": event.session_id,
            "submission_id": event.submission_id,
            "payload": payload,
        }
        try:
            text = json.dumps(event_data, ensure_ascii=False)
        except TypeError:
            event_data["payload"] = "<non-serializable payload>"
            text = json.dumps(event_data, ensure_ascii=False)
        logger.info(text)

    def shutdown(self) -> None:
        return None

    def force_flush(self) -> None:
        return None
