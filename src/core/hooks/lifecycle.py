"""Business-semantic hook interface."""

from __future__ import annotations

import abc
from typing import Any, Dict

from .context import HookContext


class HooksBase(abc.ABC):
    """Lifecycle hooks for session/task/turn/llm/tool."""

    def on_session_start(self, context: HookContext) -> None:
        return None

    def on_session_stop(self, context: HookContext) -> None:
        return None

    def on_task_start(self, context: HookContext) -> None:
        return None

    def on_task_complete(self, context: HookContext) -> None:
        return None

    def on_turn_start(self, context: HookContext) -> None:
        return None

    def on_turn_complete(self, context: HookContext) -> None:
        return None

    def on_llm_start(self, context: HookContext) -> None:
        return None

    def on_llm_complete(self, context: HookContext) -> None:
        return None

    def on_tool_start(self, context: HookContext) -> None:
        return None

    def on_tool_complete(self, context: HookContext) -> None:
        return None

    def on_error(self, context: HookContext) -> None:
        return None
