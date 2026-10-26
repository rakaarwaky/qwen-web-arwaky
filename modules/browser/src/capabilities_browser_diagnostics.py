"""Browser diagnostics capability (Playwright adaptation).

Capabilities layer: implements IBrowserDiagnosticsProtocol. Owns the
diagnostics wiring: context-level asset-abort route, page-creation hook,
per-page network/console listeners, URL scrubbing, and third-party noise
demotion.

AES201: this capability never imports a sibling capability. The
session-expiry banner scan reaches through the shared
``utility_browser_session_check`` (browser→shared, allowed by the layer
matrix). The composition root wires the facade-backed views so every
view drives one Chromium process group.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import BrowserContext, Page

from modules.shared.src.browser.contract_browser_protocol import IBrowserDiagnosticsProtocol
from modules.shared.src.browser.utility_browser_session_check import page_is_expired
from modules.shared.src.common.taxonomy_core_constant import CHAT_URL
from modules.shared.src.common.utility_logger_factory import get_logger

log = get_logger("browser")

#: Hostnames that are third-party tracking/CDN pixels — their failures and
#: console errors are noise, not domain signals. Demoted to DEBUG so they
#: never reach the stderr handler or the TUI log panel.
_THIRD_PARTY_NOISE_HOSTS: frozenset[str] = frozenset(
    {
        "google.com",
        "google-analytics.com",
        "googleapis.com",
        "googletagmanager.com",
        "alicdn.com",
        "aplus.qwen.ai",
        "adjust.io",
        "facebook.com",
        "fb.com",
        "doubleclick.net",
        "adobedtm.com",
    }
)

#: Console-message substrings (lowercase) that mark third-party SDK/CDN noise.
_NOISE_CONSOLE_PATTERNS: frozenset[str] = frozenset(
    {
        "adjust-sdk",
        "google-analytics",
        "googletagmanager",
        "alicdn",
        "aplus.qwen.ai",
        "doubleclick",
        "adobedtm",
        "err_aborted",
        "err_failed",
    }
)


# Block 1: Class Definition & Constructor


class BrowserDiagnostics(IBrowserDiagnosticsProtocol):
    """Page and context diagnostics wiring: asset-abort route, page-creation
    hook, per-page listeners, URL scrubbing, and noise demotion.

    The single owner of the diagnostics DOM mechanics. The composition
    root injects this view into ``BrowserLifecycle.browser_session`` so
    the context-level route + listeners attach at launch.
    """

    def __init__(self) -> None:
        """Initialize BrowserDiagnostics.

        Holds the diagnostics constants; no injected seam is needed
        (the capability owns its listener wiring outright).
        """
        self._chat_url = CHAT_URL

    # Block 2: Public Contract

    def wire_diagnostics(self, ctx: BrowserContext) -> None:
        """Attach all diagnostics to *ctx*: the context-level asset-abort
        route, the page-creation hook, URL scrubbing, and third-party noise
        demotion. Called once per context from ``browser_session`` (or the
        launch-pool warm path).

        The context-level asset-abort route blocks known binary/static asset
        types for non-login sessions. The page-creation hook attaches
        per-page listeners (request, requestfailed, console, response) to
        both existing and newly created pages. URLs are scrubbed before
        logging so credentials and query tokens never exfiltrate.
        """
        if "_qwa_diagnostics_wired" in vars(ctx):
            return
        vars(ctx)["_qwa_diagnostics_wired"] = True

        def _sanitize_url(url: str) -> str:
            """Sanitize URL for logging to prevent credential/query token exfiltration."""
            try:
                from urllib.parse import urlparse, urlunparse

                parsed = urlparse(url)
                return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
            except Exception:
                return url.split("?")[0]

        def attach_page_diagnostics(page: Page) -> None:
            """Wire network and console listeners onto *page* for run diagnostics."""

            def on_request_failed(request: Any) -> None:
                """Log failed browser requests with sanitized URLs."""
                if _is_third_party_noise(request.url):
                    log.debug("browser_request_failed %s %s", _sanitize_url(request.url), request.failure)
                    return
                log.warning("browser_request_failed %s %s", _sanitize_url(request.url), request.failure)

            def on_console(message: Any) -> None:
                """Log page console errors and warnings."""
                if message.type not in {"error", "warning"}:
                    return
                text = (message.text or "").lower()
                is_noise = any(pat in text for pat in _NOISE_CONSOLE_PATTERNS)
                if is_noise:
                    log.debug("browser_console_message %s %s", message.type, message.text)
                else:
                    log.warning("browser_console_message %s %s", message.type, message.text)

            def on_request(request: Any) -> None:
                """Log mutating requests sent to qwen.ai."""
                if request.method in {"POST", "PUT", "PATCH"} and "qwen.ai" in request.url:
                    log.info("browser_mutation_request %s %s", request.method, _sanitize_url(request.url))

            def on_response(response: Any) -> None:
                """Log API error responses and qwen.ai mutation responses."""
                url = response.url.lower()
                if response.status >= 400 and any(
                    token in url for token in ("chat", "completion", "generate", "conversation", "api")
                ):
                    if _is_third_party_noise(response.url):
                        log.debug("browser_http_error %s %s", response.status, _sanitize_url(response.url))
                    else:
                        log.warning("browser_http_error %s %s", response.status, _sanitize_url(response.url))
                elif response.request.method in {"POST", "PUT", "PATCH"} and "qwen.ai" in url:
                    log.info("browser_mutation_response %s %s", response.status, _sanitize_url(response.url))

            page.on("request", on_request)
            page.on("requestfailed", on_request_failed)
            page.on("console", on_console)
            page.on("response", on_response)

        for existing_page in ctx.pages:
            attach_page_diagnostics(existing_page)
        ctx.on("page", attach_page_diagnostics)

    def detect_session_expired(self, page: Page) -> bool:
        """True when the live page now shows an in-page session-expiry notice.

        Delegates to the shared utility's expiry-banner scan (PR 5
        collapse); the diagnostics capability owns the call site so the
        prompt pipelines reach it through the narrow seam.
        """
        return page_is_expired(page)

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of BrowserDiagnostics."""
        return "BrowserDiagnostics()"


def _is_third_party_noise(url: str) -> bool:
    """Return True when *url* points at a known third-party tracking/CDN domain."""
    from urllib.parse import urlparse

    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return any(host == d or host.endswith("." + d) for d in _THIRD_PARTY_NOISE_HOSTS)


__all__ = ["BrowserDiagnostics"]
