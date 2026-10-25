"""Browser navigation capability (Playwright adaptation).

Capabilities layer: implements IBrowserNavigationProtocol. Narrow view over
the browser seam: goto, auth assert, page reset, and the manual login window.

The capability does not import the browser adapter (AES201). It holds the
injected ``IBrowserProtocol`` facade and reaches the Playwright mechanics
through it; the composition root wires the concrete ``BrowserAdapter`` into
both views so a caller that holds only the navigation view still drives one
Chromium process group.
"""

from __future__ import annotations

from contextlib import AbstractContextManager

from playwright.sync_api import Page

from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserNavigationProtocol,
    IBrowserProtocol,
)
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_vo import AppConfig


class BrowserNavigation(IBrowserNavigationProtocol):
    """Page navigation, authentication assert, and new-chat reset.

    Delegates to the injected ``IBrowserProtocol`` facade; the container owns
    the seam and injects the same concrete adapter into every narrow view.
    """

    # Block 1: Class Definition & Constructor

    def __init__(self, browser: IBrowserProtocol) -> None:
        """Initialize BrowserNavigation.

        *browser* is the facade that owns the Playwright process group;
        this view exposes only the navigation half of it.
        """
        self._browser = browser

    # Block 2: Public Contract

    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate *page* to the chat, assert auth, reset to a clean conversation."""
        self._browser.navigate_to_chat(page, emitter)

    def check_auth(self, page: Page) -> None:
        """Raise ``AuthRequiredError`` when *page* is not authenticated."""
        self._browser.check_auth(page)

    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset *page* to a clean chat state."""
        self._browser.reset_page(page, emitter)

    def open_login_page(self, cfg: AppConfig) -> AbstractContextManager[Page]:
        """Open one fresh page on *cfg*'s profile and go to the chat URL."""
        return self._browser.open_login_page(cfg)

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of BrowserNavigation."""
        return "BrowserNavigation()"


__all__ = ["BrowserNavigation"]
