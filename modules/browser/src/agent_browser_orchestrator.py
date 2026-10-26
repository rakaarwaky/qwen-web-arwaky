"""Agent: authenticate a browser session so callers never repeat the sequence.

Each prompt and session orchestrator used to open a Chromium context, pick a
page, navigate to the chat, and prove the saved session was still signed in —
four steps repeated in six files. This orchestrator owns that sequence once
and exposes it as a single context manager, so no caller can forget the
authentication check that every DOM interaction depends on.

The orchestrator is also the composition point for the legacy
``IBrowserProtocol`` facade: it owns the four narrow capability views
(``BrowserLifecycle``, ``BrowserNavigation``, ``BrowserModelPolicy``,
``BrowserDiagnostics``) and implements ``IBrowserProtocol`` by delegating
every facade method to the owning narrow capability. The facade stays in the
Agent layer so no capabilities-layer file imports a sibling capability
(AES201); the composition root constructs the narrow views and hands them
here.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import BrowserContext, Page

from modules.shared.src.browser.contract_browser_aggregate import IBrowserAggregate
from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserDiagnosticsProtocol,
    IBrowserLifecycleProtocol,
    IBrowserModelPolicyProtocol,
    IBrowserNavigationProtocol,
    IBrowserProtocol,
)
from modules.shared.src.browser.utility_browser_session_check import (
    assert_on_chat_page,
    session_is_alive,
)
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.common.taxonomy_core_vo import AppConfig, ModelLabel, WaitTimeoutMs
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol

log = get_logger("browser")

__all__ = ["BrowserOrchestrator"]


class BrowserOrchestrator(IBrowserAggregate, IBrowserProtocol):
    """Open authenticated chat sessions on behalf of the other orchestrators.

    Implements ``IBrowserAggregate`` (``open_session``) and the legacy
    ``IBrowserProtocol`` facade. The facade methods delegate to the four
    narrow capability views injected by the composition root, so the
    orchestrator owns no DOM mechanics of its own.
    """

    def __init__(
        self,
        browser: IBrowserProtocol | None,
        observability: IObservabilityProtocol,
        *,
        lifecycle: IBrowserLifecycleProtocol,
        navigation: IBrowserNavigationProtocol,
        model_policy: IBrowserModelPolicyProtocol,
        diagnostics: IBrowserDiagnosticsProtocol,
    ) -> None:
        """Wrap the browser capability that does the Playwright work.

        *browser* is the facade the orchestrator's own ``open_session``
        drives (the composition root passes the orchestrator itself so the
        facade and the aggregate share one view set); *observability*
        owns the run-scoped log. The four narrow views are the single-owner
        seams every facade method reaches through.
        """
        self._browser = browser if browser is not None else self
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

    # ── IBrowserProtocol facade (delegates to the narrow views) ───────

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
        """Open one fresh page on *cfg*'s profile and go to the chat URL.

        Delegates to the navigation capability, which uses the
        *lifecycle* view for ``browser_session`` when provided, and falls
        back to the orchestrator's own lifecycle view when omitted so the
        loop stays on one Chromium process group.
        """
        if lifecycle is None:
            return self._navigation.open_login_page(cfg, lifecycle=self._lifecycle)
        return self._navigation.open_login_page(cfg, lifecycle=lifecycle)

    def open_chat_page(self, page: Page, *, strict: bool = True) -> None:
        """Navigate *page* to the chat URL and assert authentication."""
        self._navigation.open_chat_page(page, strict=strict)

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
        """True when the live page now shows an in-page session-expiry notice.

        Delegates to the diagnostics capability, which reaches the shared
        utility's expiry-banner scan (PR 5 collapse).
        """
        return self._diagnostics.detect_session_expired(page)

    def check_session(self, page: Page) -> bool:
        """Return True when *page* shows the authenticated chat UI.

        Routes through the shared utility (PR 5 collapse): the URL /
        login-form / in-page expiry-banner assert plus the live chat-input
        check live in ``utility_browser_session_check``; the facade owns
        no DOM logic of its own.
        """
        try:
            try:
                page.wait_for_load_state("load", timeout=15_000)
            except Exception:
                log.debug("session_load_state_wait_failed")
            assert_on_chat_page(page)
            return session_is_alive(page)
        except AuthRequiredError:
            return False
        except Exception as exc:
            log.warning("session_validation_failed %s", str(exc))
            return False

    # Internal DOM-mechanic helpers the legacy monolith exposed to tests;
    # each now reaches through the owning capability.

    def _goto_chat(self, page: Page, navigation_timeout_ms: int, load_timeout_ms: int) -> None:
        """Navigate to chat.qwen.ai without waiting on third-party page assets."""
        cast(Any, self._navigation)._goto_chat(page, navigation_timeout_ms, load_timeout_ms)

    def _start_new_chat(self, page: Page, opt_in: bool = True) -> None:
        """Start a clean Qwen conversation so stale cards cannot affect monitoring."""
        cast(Any, self._navigation)._start_new_chat(page, opt_in)

    def _clean_stale_locks(self, user_data_dir: str) -> None:
        """Clean up stale Chromium lock files if process crashed or before launch."""
        cast(Any, self._lifecycle)._clean_stale_locks(user_data_dir)

    def _launch_context(self, p: object, kwargs: dict[str, object]) -> BrowserContext:
        """Launch the persistent context with tenacity retry for transient crashes."""
        return cast(Any, self._lifecycle)._launch_context(p, kwargs)  # type: ignore[no-any-return]

    def _launch_kwargs(self, session_dir: Path, cfg: AppConfig) -> dict[str, object]:
        """Build the persistent-context launch arguments for *cfg*."""
        return cast(Any, self._lifecycle)._launch_kwargs(session_dir, cfg)  # type: ignore[no-any-return]

    def _open_chat_page(
        self,
        cfg: AppConfig,
        *,
        _mode: str,
        strict_auth: bool,
        session_path: Path | None = None,
    ) -> Iterator[Page]:
        """The shared launch → navigate → auth-assert sequence for one profile."""
        return cast(Any, self._lifecycle)._open_chat_page(
            cfg, _mode=_mode, strict_auth=strict_auth, session_path=session_path
        )  # type: ignore[no-any-return]

    def _verify_default_model(self, page: Page, require_switch: bool = True) -> tuple[bool, str]:
        """Confirm the active model is the configured default, degrading when it is not."""
        target = self._model_policy.target_model()
        verified, detected = self._model_policy.verify_default_model(page, target, require_switch)
        return verified, str(detected)

    def _select_first_available_model(self, page: Page) -> str | None:
        """Select the first model the picker offers, or return None when unreadable."""
        result = self._model_policy.select_first_available_model(page)
        return None if result is None else str(result)

    def _wait_for_model_picker_ready(self, page: Page, timeout_ms: int = 15_000) -> None:
        """Wait until the hydrated picker exposes the configured default option."""
        self._model_policy.wait_for_picker_ready(page, WaitTimeoutMs(timeout_ms))

    def _retry_default_model_selection(self, page: Page) -> None:
        """Close a stale picker, allow hydration, and retry default-model selection."""
        self._model_policy.retry_default_model_selection(page)

    def _get_model_trigger(self, page: Page) -> object:
        """Return locator for active model selector trigger button/div."""
        return self._model_policy.get_model_trigger(page)

    def _try_set_as_default(self, page: Page) -> None:
        """Best-effort attempt to click 'Set default' or 'Set as default' in Qwen UI picker."""
        self._model_policy.try_set_as_default(page)

    def __repr__(self) -> str:
        """Return string representation of BrowserOrchestrator."""
        return "BrowserOrchestrator()"


def _raise_if_session_expired(page: Page) -> None:
    """Raise AuthRequiredError when the in-page expiry banner is detected."""
    from modules.shared.src.browser.utility_browser_session_check import (
        _in_page_expiry_banner_visible,
    )

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
