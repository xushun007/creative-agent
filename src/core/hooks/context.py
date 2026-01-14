"""Hook context data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class HookContext:
    """Context payload for hook callbacks."""

    name: str
    session_id: str
    submission_id: Optional[str]
    timestamp: str
    payload: Dict[str, Any]

    @classmethod
    def create(
        cls,
        name: str,
        session_id: str,
        submission_id: Optional[str],
        payload: Optional[Dict[str, Any]] = None,
    ) -> "HookContext":
        timestamp = datetime.now(timezone.utc).isoformat()
        return cls(
            name=name,
            session_id=session_id,
            submission_id=submission_id,
            timestamp=timestamp,
            payload=payload or {},
        )
