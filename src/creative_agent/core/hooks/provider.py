"""Hook provider for lifecycle hooks."""

from __future__ import annotations

from typing import Iterable, Optional

from creative_agent.utils.logger import logger

from .context import HookContext
from .lifecycle import HooksBase
from .processors import LoggerHooks


class HookProvider:
    """Manages lifecycle hooks and dispatches events."""

    def __init__(self, disabled: bool = False, with_default_processors: bool = True) -> None:
        self._disabled = disabled
        self._hooks: tuple[HooksBase, ...] = ()
        if with_default_processors:
            self.register_hook(LoggerHooks())

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = disabled

    def register_hook(self, hook: HooksBase) -> None:
        self._hooks += (hook,)

    def set_hooks(self, hooks: Iterable[HooksBase]) -> None:
        self._hooks = tuple(hooks)

    def on_session_start(self, session_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_session_start", session_id, None, payload or {})

    def on_session_stop(self, session_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_session_stop", session_id, None, payload or {})

    def on_task_start(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_task_start", session_id, submission_id, payload or {})

    def on_task_complete(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_task_complete", session_id, submission_id, payload or {})

    def on_turn_start(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_turn_start", session_id, submission_id, payload or {})

    def on_turn_complete(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_turn_complete", session_id, submission_id, payload or {})

    def on_llm_start(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_llm_start", session_id, submission_id, payload or {})

    def on_llm_complete(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_llm_complete", session_id, submission_id, payload or {})

    def on_tool_start(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_tool_start", session_id, submission_id, payload or {})

    def on_tool_complete(self, session_id: str, submission_id: str, payload: Optional[dict] = None) -> None:
        self._dispatch("on_tool_complete", session_id, submission_id, payload or {})

    def on_error(self, session_id: str, submission_id: Optional[str], payload: Optional[dict] = None) -> None:
        self._dispatch("on_error", session_id, submission_id, payload or {})

    def _dispatch(self, method: str, session_id: str, submission_id: Optional[str], payload: dict) -> None:
        if self._disabled:
            return
        event_name = method.replace("on_", "", 1)
        context = HookContext.create(
            name=event_name.replace("_", "."),
            session_id=session_id,
            submission_id=submission_id,
            payload=payload,
        )
        for hook in self._hooks:
            try:
                getattr(hook, method)(context)
            except Exception as exc:
                logger.error(f"Hook handler {hook.__class__.__name__}.{method} failed: {exc}")
