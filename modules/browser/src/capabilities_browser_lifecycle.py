"""Browser lifecycle capability (Playwright adaptation).

Capabilities layer: implements IBrowserLifecycleProtocol. Narrow view over
the browser seam: launch/teardown, ephemeral-context probes, and
master-profile renewal.

The capability does not import the browser adapter (AES201). It holds the
injected ``IBrowserProtocol`` facade and reaches the Playwright mechanics
through it; the composition root wires the concrete ``BrowserAdapter`` into
both views so a caller that holds only the lifecycle view still drives one
Chromium process group.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserLifecycleProtocol,
    IBrowserProtocol,
)
from modules.shared.src.common.taxonomy_core_vo import AppConfig


class BrowserLifecycle(IBrowserLifecycleProtocol):
    """Launch/teardown, ephemeral-context probes, and master-profile renewal.

    Delegates to the injected ``IBrowserProtocol`` facade; the container owns
    the seam and injects the same concrete adapter into every narrow view.
    """

    # Block 1: Class Definition & Constructor

    def __init__(self, browser: IBrowserProtocol) -> None:
        """Initialize BrowserLifecycle.

        *browser* is the facade that owns the Playwright process group;
        this view exposes only the lifecycle half of it.
        """
        self._browser = browser

    # Block 2: Public Contract

    def browser_session(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> AbstractContextManager[BrowserContext]:
        """Launch an isolated persistent Chromium context for *cfg*."""
        return self._browser.browser_session(cfg, session_path, executable_path)

    def health_probe_page(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> AbstractContextManager[Page]:
        """Open one fresh, authenticated chat page on *cfg*'s session profile."""
        return self._browser.health_probe_page(cfg, session_path, executable_path)

    def renew_session(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> None:
        """Renew session credentials on *cfg*'s master profile in place."""
        self._browser.renew_session(cfg, session_path, executable_path)

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of BrowserLifecycle."""
        return "BrowserLifecycle()"


__all__ = ["BrowserLifecycle"]
