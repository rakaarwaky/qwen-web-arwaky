"""Browser-domain aggregate contract (AES101 `_aggregate`).

``IBrowserAggregate`` is the single entry point over the browser feature.
The CLI and MCP surfaces call :meth:`open_session`; the agent behind it
owns the launch → navigate → auth-check sequence, so no surface can
forget the authentication check every DOM interaction depends on.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager

from playwright.sync_api import Page

from modules.shared.src.taxonomy_core_vo import AppConfig


class IBrowserAggregate(ABC):
    """Single entry point over the browser feature.

    Exactly one method: the door consumers knock on. Adding a consumer
    verb means adding a method here, not a second dispatch parameter.
    """

    @abstractmethod
    def open_session(self, cfg: AppConfig) -> AbstractContextManager[Page]:
        """Context manager yielding an authenticated ``chat.qwen.ai`` page.

        The context owns the Chromium process group: entering launches the
        persistent context, navigates to the chat, and proves the saved
        session is still authenticated; exiting tears the browser down even
        when the caller's body raises.
        """
        ...


__all__ = ["IBrowserAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IBrowserAggregate": IBrowserAggregate,
}
