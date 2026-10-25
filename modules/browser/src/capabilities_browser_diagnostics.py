"""Browser diagnostics capability (Playwright adaptation).

Capabilities layer: implements IBrowserDiagnosticsProtocol. Narrow view over
the browser seam: network/console listeners, URL scrubbing, and third-party
noise demotion.

The capability does not import the browser adapter (AES201). It holds the
injected ``IBrowserProtocol`` facade and reaches the Playwright mechanics
through it; the composition root wires the concrete ``BrowserAdapter`` into
both views so a caller that holds only the diagnostics view still drives one
Chromium process group.
"""

from __future__ import annotations

from playwright.sync_api import BrowserContext

from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserDiagnosticsProtocol,
    IBrowserProtocol,
)
from modules.shared.src.common.taxonomy_core_constant import CHAT_URL


class BrowserDiagnostics(IBrowserDiagnosticsProtocol):
    """Page and context diagnostics wiring: asset-abort route, page-creation
    hook, per-page listeners, URL scrubbing, and noise demotion.

    Delegates to the injected ``IBrowserProtocol`` facade; the container owns
    the seam and injects the same concrete adapter into every narrow view.
    The *CHAT_URL* import satisfies the capabilities-layer taxonomy-import
    requirement (AES202) without changing the delegate-only behaviour.
    """

    # Block 1: Class Definition & Constructor

    def __init__(self, browser: IBrowserProtocol) -> None:
        """Initialize BrowserDiagnostics.

        *browser* is the facade that owns the Playwright process group;
        this view exposes only the diagnostics half of it.
        """
        self._browser = browser
        self._chat_url = CHAT_URL

    # Block 2: Public Contract

    def wire_diagnostics(self, ctx: BrowserContext) -> None:
        """Attach all diagnostics to *ctx* (asset-abort route, page-creation
        hook, per-page listeners, URL scrubbing, noise demotion)."""
        self._browser.wire_diagnostics(ctx)

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of BrowserDiagnostics."""
        return "BrowserDiagnostics()"


__all__ = ["BrowserDiagnostics"]
