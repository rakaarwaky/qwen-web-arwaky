"""Capabilities: page-level session liveness/auth probe (FR-BROWSER-002).

``SessionCheck`` binds the shared ``utility_browser_session_check`` DOM
probes (``session_is_alive`` / ``assert_on_chat_page``) to a Playwright
page. No DOM mechanics of its own. One protocol per file (AES403).
"""

from __future__ import annotations

from playwright.sync_api import Page

from modules.shared.src.browser.contract_browser_protocol import ISessionCheckProtocol
from modules.shared.src.browser.utility_browser_session_check import (
    assert_on_chat_page,
    session_is_alive,
)
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError


# Block 1: Class Definition & Constructor
class SessionCheck(ISessionCheckProtocol):
    """Validates that the browser session and Qwen chat UI are alive.

    Binds the shared ``utility_browser_session_check`` DOM probes
    (``session_is_alive`` / ``assert_on_chat_page``) to a Playwright
    page. No DOM mechanics of its own.
    """

    def __init__(self, page: Page) -> None:
        """Initialize with a Playwright Page instance."""
        self.page = page

    # Block 2: Protocol Method Implementation
    def is_alive(self) -> bool:
        """Return True if the session is stable and the chat UI is responsive."""
        return session_is_alive(self.page)

    def check_auth(self) -> None:
        """Raise AuthRequiredError if the session is no longer authenticated or UI is missing."""
        try:
            assert_on_chat_page(self.page)
        except Exception as exc:
            raise AuthRequiredError(f"Session invalid (browser error): {exc}") from exc

    # Block 3: Dunder Methods, Factories & Helpers
    def __repr__(self) -> str:
        """Return string representation of SessionCheck."""
        return f"SessionCheck(page={self.page!r})"


__all__ = ["SessionCheck"]
