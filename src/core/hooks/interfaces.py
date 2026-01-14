"""Hook interfaces and data models."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class HookEvent:
    """Lightweight hook event envelope."""

    name: str
    timestamp: str
    session_id: str
    submission_id: Optional[str]
    payload: Dict[str, Any]

    @classmethod
    def create(
        cls,
        name: str,
        session_id: str,
        submission_id: Optional[str],
        payload: Optional[Dict[str, Any]] = None,
    ) -> "HookEvent":
        timestamp = datetime.now(timezone.utc).isoformat()
        return cls(
            name=name,
            timestamp=timestamp,
            session_id=session_id,
            submission_id=submission_id,
            payload=payload or {},
        )


class HookProcessor(abc.ABC):
    """Interface for receiving hook events."""

    @abc.abstractmethod
    def on_event(self, event: HookEvent) -> None:
        """Handle a hook event."""
        raise NotImplementedError

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Cleanup resources."""
        raise NotImplementedError

    @abc.abstractmethod
    def force_flush(self) -> None:
        """Flush any buffered state."""
        raise NotImplementedError
