"""Agent: authenticate a browser session so callers never repeat the sequence.

Each prompt and session orchestrator used to open a Chromium context, pick a
page, navigate to the chat, and prove the saved session was still signed in —
four steps repeated in six files. This orchestrator owns that sequence once
and exposes it as a single context manager, so no caller can forget the
authentication check that every DOM interaction depends on.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from playwright.sync_api import BrowserContext, Page

from modules.shared.src.browser.contract_browser_aggregate import IBrowserAggregate
from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserDiagnosticsProtocol,
    IBrowserLifecycleProtocol,
    IBrowserModelPolicyProtocol,
    IBrowserNavigationProtocol,
)
from modules.shared.src.browser.utility_browser_session_check import _in_page_expiry_banner_visible
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.common.taxonomy_core_vo import AppConfig, ModelLabel, WaitTimeoutMs
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol

log = get_logger("browser")

__all__ = ["BrowserOrchestrator"]


class BrowserOrchestrator(IBrowserAggregate):
    """Open authenticated chat sessions on behalf of the other orchestrators.

    Implements ``IBrowserAggregate`` (``open_session``). The diagnostics
    probe (``detect_session_expired``) is routed through the injected
    narrow protocol views so the Agent layer carries no inline DOM
    mechanics and no legacy ``IBrowserProtocol`` facade. Capability
    internals are reached only through the injected narrow protocol
    views; this orchestrator is ignorant of capability implementations.
    """

    def __init__(
        self,
        observability: IObservabilityProtocol,
        *,
        lifecycle: IBrowserLifecycleProtocol,
        navigation: IBrowserNavigationProtocol,
        model_policy: IBrowserModelPolicyProtocol,
        diagnostics: IBrowserDiagnosticsProtocol,
    ) -> None:
        """Wrap the browser capability that does the Playwright work.

        *observability* owns the run-scoped log. The four narrow views are
        the single-owner seams every delegate reaches through.
        """
        self._observability = observability
        self._lifecycle = lifecycle
        self._navigation = navigation
        self._model_policy = model_policy
        self._diagnostics = diagnostics

    @contextmanager
    def open_session(self, cfg: AppConfig) -> Iterator[Page]:
        """Yield a page already navigated to the chat and proven authenticated.

        Entering launches the persistent Chromium context and yields the first
        page, or a new one when the context starts empty. Navigation and the
        auth check run before the page is handed over, so a caller receiving a
        page is guaranteed a signed-in chat. Exiting tears the context down even
        when the caller's body raises, which is what keeps a failed run from
        leaking Chromium processes.
        """
        with self._lifecycle.browser_session(cfg) as bctx:
            yield self._first_page(bctx)

    def _first_page(self, bctx: BrowserContext) -> Page:
        """Return the context's first page, creating one when it has none.

        A freshly launched persistent context usually exposes about:blank, but
        a restored profile can start with none, and every caller needs a page
        to work with, so the fallback keeps one code path for both cases.
        """
        if getattr(bctx, "pages", None):
            return bctx.pages[0]
        return bctx.new_page()

    # ── Delegates to narrow capability views (public surface only) ───────

    def browser_session(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> AbstractContextManager[BrowserContext]:
        """Launch an isolated persistent Chromium context for *cfg*."""
        return self._lifecycle.browser_session(cfg, session_path, executable_path)

    def health_probe_page(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> AbstractContextManager[Page]:
        """Open one fresh, authenticated chat page on *cfg*'s session profile."""
        return self._lifecycle.health_probe_page(cfg, session_path, executable_path)

    def renew_session(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> None:
        """Renew session credentials on *cfg*'s master profile in place."""
        self._lifecycle.renew_session(cfg, session_path, executable_path)

    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate *page* to the chat, select the model, emit startup events."""
        self._navigation.navigate_to_chat(page, emitter)

    def check_auth(self, page: Page) -> None:
        """Raise ``AuthRequiredError`` when *page* is not authenticated."""
        self._navigation.check_auth(page)

    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset *page* to a clean chat state."""
        self._navigation.reset_page(page, emitter)

    def open_login_page(
        self, cfg: AppConfig, lifecycle: IBrowserLifecycleProtocol | None = None
    ) -> AbstractContextManager[Page]:
        """Open one fresh page on *cfg*'s profile and go to the chat URL."""
        if lifecycle is None:
            return self._navigation.open_login_page(cfg, lifecycle=self._lifecycle)
        return self._navigation.open_login_page(cfg, lifecycle=lifecycle)

    def select_model(self, page: Page, emitter: LifecycleEmitter) -> ModelLabel:
        """Read/select the default model on *page*; return the chosen label."""
        return self._model_policy.select_model(page, emitter)

    def verify_model(self, page: Page, expected: ModelLabel) -> bool:
        """Return True when *page* shows *expected* as the active model."""
        return self._model_policy.verify_model(page, expected)

    def verify_default_model(
        self, page: Page, target: ModelLabel, require_switch: bool = True
    ) -> tuple[bool, ModelLabel]:
        """Confirm the active model is *target*, degrading when it is not."""
        return self._model_policy.verify_default_model(page, target, require_switch)

    def select_first_available_model(self, page: Page) -> ModelLabel | None:
        """Select the first model the picker offers, or return None when unreadable."""
        return self._model_policy.select_first_available_model(page)

    def wait_for_picker_ready(self, page: Page, timeout_ms: WaitTimeoutMs = WaitTimeoutMs(15_000)) -> None:
        """Wait until the hydrated picker exposes the configured default option."""
        self._model_policy.wait_for_picker_ready(page, timeout_ms)

    def retry_default_model_selection(self, page: Page) -> None:
        """Close a stale picker, allow hydration, and retry default-model selection."""
        self._model_policy.retry_default_model_selection(page)

    def get_model_trigger(self, page: Page) -> object:
        """Return the locator for the active model selector trigger button/div."""
        return self._model_policy.get_model_trigger(page)

    def try_set_as_default(self, page: Page) -> None:
        """Best-effort attempt to click 'Set default' in the Qwen UI picker."""
        self._model_policy.try_set_as_default(page)

    def ensure_default_model(self, page: Page) -> bool:
        """Best-effort: click the configured default option in the picker."""
        return self._model_policy.ensure_default_model(page)

    def wire_diagnostics(self, ctx: BrowserContext) -> None:
        """Attach all diagnostics to *ctx* (asset-abort route, page-creation
        hook, per-page listeners, URL scrubbing, noise demotion)."""
        self._diagnostics.wire_diagnostics(ctx)

    def detect_session_expired(self, page: Page) -> bool:
        """True when the live page now shows an in-page session-expiry notice."""
        return self._diagnostics.detect_session_expired(page)

    def __repr__(self) -> str:
        """Return string representation of BrowserOrchestrator."""
        return "BrowserOrchestrator()"


def _raise_if_session_expired(page: Page) -> None:
    """Raise AuthRequiredError when the in-page expiry banner is detected."""
    if _in_page_expiry_banner_visible(page):
        raise AuthRequiredError(
            "Session expired — the saved Qwen login session is no longer valid "
            f"(in-page notice detected on {page.url}). "
            "Run `qwen-web-arwaky session login` to re-authenticate, then retry.",
            session_expired=True,
        )


def _active_model() -> str:
    """Return the model a running pipeline should target.

    Delegates to the shared utility, so the per-run target model stays in
    one place.
    """
    from modules.shared.src.browser.utility_browser_model_target import target_model

    return str(target_model())


__all__ = ["BrowserOrchestrator", "_raise_if_session_expired", "_active_model"]
