"""Global hook provider accessors."""

from __future__ import annotations

from typing import Optional

from .provider import HookProvider


_GLOBAL_HOOK_PROVIDER: Optional[HookProvider] = None


def set_hook_provider(provider: HookProvider) -> None:
    global _GLOBAL_HOOK_PROVIDER
    _GLOBAL_HOOK_PROVIDER = provider


def get_hook_provider() -> HookProvider:
    global _GLOBAL_HOOK_PROVIDER
    if _GLOBAL_HOOK_PROVIDER is None:
        _GLOBAL_HOOK_PROVIDER = HookProvider()
    return _GLOBAL_HOOK_PROVIDER
