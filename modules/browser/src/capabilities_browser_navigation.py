"""Browser navigation capability (Playwright adaptation).

Capabilities layer: implements IBrowserNavigationProtocol. Owns page
navigation mechanics: goto, auth assert, new-chat reset, and the manual
login window.

AES201: this capability never imports a sibling capability. The
model-selection step inside ``navigate_to_chat`` reaches the picker
readiness wait through the injected ``IBrowserModelPolicyProtocol``; the
launch + teardown needed by ``open_login_page`` reach through the
injected ``IBrowserLifecycleProtocol``. The composition root wires the
facade-backed views so every view drives one Chromium process group.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from playwright.sync_api import (
    Error,
    Page,
)

from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserLifecycleProtocol,
    IBrowserModelPolicyProtocol,
    IBrowserNavigationProtocol,
)
from modules.shared.src.browser.utility_browser_model_target import target_model
from modules.shared.src.browser.utility_browser_session_check import assert_on_chat_page
from modules.shared.src.common.taxonomy_core_constant import (
    CHAT_URL,
    NAVIGATION_LOAD_TIMEOUT_MS,
    NAVIGATION_TIMEOUT_MS,
    NEW_CHAT_SELECTORS,
    TEXTAREA_SELECTOR,
)
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import (
    AuthRequiredError,
)
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_NETWORK_RECONNECTING,
    EVENT_SESSION_EXPIRED,
    EVENT_WEB_LOADED,
)
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.common.utility_dom_helper import click_first_visible_enabled
from modules.shared.src.common.utility_logger_factory import get_logger

log = get_logger("browser.navigation")


# Block 1: Class Definition & Constructor


class BrowserNavigation(IBrowserNavigationProtocol):
    """Page navigation, authentication assert, and new-chat reset.

    Owns the goto / auth-assert / reset / login-window DOM mechanics.
    The model-selection step inside ``navigate_to_chat`` is reached
    through the injected ``IBrowserModelPolicyProtocol`` (AES201: no
    sibling-capability import — the container wires the shared view).
    """

    def __init__(
        self,
        model_policy: IBrowserModelPolicyProtocol,
        lifecycle: IBrowserLifecycleProtocol | None = None,
    ) -> None:
        """Initialize BrowserNavigation.

        *model_policy* is the injected model-policy capability that owns
        the issue #283/#374 model selection/verification fallback rules.
        *lifecycle* is the injected launch/teardown capability used by
        ``open_login_page`` to obtain a ``browser_session``; when omitted
        the capability falls back to its own launch path.
        """
        self._model_policy = model_policy
        self._lifecycle = lifecycle

    # Block 2: Public Contract

    def open_chat_page(self, page: Page, *, strict: bool = True) -> None:
        """Navigate *page* to the chat URL and assert authentication.

        Runs ``_goto_chat`` (up to 4 attempts with exponential backoff)
        then one authentication assertion. ``strict`` mirrors the two
        consumers: renewal asserts on the chat page (strict), the health
        probe tolerates a page that is still hydrating (non-strict).
        """
        self._goto_chat(page, NAVIGATION_TIMEOUT_MS, NAVIGATION_LOAD_TIMEOUT_MS)
        assert_on_chat_page(page, strict=strict)

    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate to chat.qwen.ai, verify session, and emit lifecycle events step-by-step:

        Step 1: Navigate to chat page
        Step 2: Start clean conversation state
        Step 3: Emit EVENT_WEB_LOADED, then assert authentication
        Step 4: Probe the in-page expiry banner; when present, emit
        EVENT_SESSION_EXPIRED and raise before LOGIN_VERIFIED is emitted.
        Otherwise emit EVENT_LOGIN_VERIFIED.
        Step 5: Select the configured default model (issue #283)
        Step 6: Verify the model is active; when the configured model is not
        offered by the picker, fall back to the first available model and log a
        WARNING instead of aborting the pipeline, marking the event
        ``fallback=True`` whenever a different model is read and aborting only
        when no model label can be read at all
        """
        # Step 1: Navigate to chat URL
        self._goto_chat(page, NAVIGATION_TIMEOUT_MS, NAVIGATION_LOAD_TIMEOUT_MS)

        # The committed document may arrive before React hydration renders the
        # input; a slow hydrate is not an operator signal, so give the
        # textarea a short grace period before the (non-strict) assert below.
        with contextlib.suppress(Error):
            page.wait_for_selector(TEXTAREA_SELECTOR, timeout=5000)

        # Step 2: Start clean conversation state. Qwen hydrates the model picker
        # asynchronously after this reset; wait for its actual default option rather
        # than sleeping for a fixed duration.
        self._start_new_chat(page)
        with contextlib.suppress(Error):
            self._model_policy.wait_for_picker_ready(page)

        # Step 3: Emit lifecycle events. WEB_LOADED marks the committed document.
        emitter.emit(EVENT_WEB_LOADED, {"url": page.url})

        # Step 4: Banner detection precedes the login-form assert so a
        # terminal EVENT_SESSION_EXPIRED lands before LOGIN_VERIFIED. The
        # login-form check still owns the not-authenticated case when the
        # banner is absent.
        try:
            assert_on_chat_page(page, strict=False)
        except AuthRequiredError as exc:
            if exc.session_expired:
                # In-page expiry banner: emit the terminal event before
                # the pipeline propagates the failure to the orchestrator.
                emitter.emit(EVENT_SESSION_EXPIRED, {"url": page.url, "reason": "in_page_banner"})
            raise
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": page.url})

        # Step 5: Select the configured default model so the user never picks
        # it manually. The model-policy capability owns the fallback rules.
        switched = self._model_policy.ensure_default_model(page)

        # Step 6: Verify the switch actually happened. A readable but different
        # model degrades to the first available picker entry with a WARNING
        # (issue #283 AC-2) instead of aborting, and the event carries
        # ``fallback=True`` so the substitution is auditable (issue #374).
        verified, detected = self._model_policy.verify_default_model(page, target_model(), require_switch=switched)
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": detected, "fallback": not verified})

    def check_auth(self, page: Page) -> None:
        """Raise AuthRequiredError if the page is on a login/auth URL or login form detected."""
        assert_on_chat_page(page)

    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset the page to a clean state by navigating back to chat.qwen.ai."""
        try:
            emitter.emit(EVENT_NETWORK_RECONNECTING, {"url": CHAT_URL})
            self._goto_chat(page, 10_000, NAVIGATION_LOAD_TIMEOUT_MS)
        except Error as e:
            log.warning("page_reset_failed %s", str(e))

    @contextmanager
    def open_login_page(self, cfg: AppConfig, lifecycle: IBrowserLifecycleProtocol | None = None) -> Iterator[Page]:
        """Open one fresh page on ``cfg``'s profile and go to the chat URL.

        Thin wrapper over ``browser_session`` + first page + ``goto``.
        Used by the manual login window flow; performs no model selection.
        No auth assertion: the page is handed to the operator to log in.
        """
        active = lifecycle if lifecycle is not None else self._lifecycle
        if active is not None:
            with active.browser_session(cfg) as ctx:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                self.open_chat_page(page, strict=False)
                yield page
                return
        # No lifecycle injected: the navigation capability falls back to
        # its own launch path (used in standalone test harnesses).
        with self._open_chat_page_standalone(cfg) as page:
            yield page

    # Block 3: Dunder Methods, Factories & Helpers

    def _goto_chat(
        self,
        page: Page,
        navigation_timeout_ms: int,
        load_timeout_ms: int,
    ) -> None:
        """Navigate to chat.qwen.ai without waiting on third-party page assets.

        ``domcontentloaded`` can remain pending when Qwen or an analytics asset
        stalls. The application only needs the committed chat document before
        its own DOM readiness checks, so navigation uses ``commit`` and treats
        the later DOMContentLoaded wait as best-effort. Up to 4 attempts with
        exponential backoff (2s, 4s, 8s) handle transient network failures.

        If the page is already on chat.qwen.ai (e.g. from eager navigation in
        browser_session), the goto is skipped and only DOM readiness is awaited.
        """
        # Fast path: eager navigation in browser_session already landed us here.
        if "chat.qwen.ai" in (page.url or ""):
            log.debug("browser_skip_goto_already_on_chat %s", page.url)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=load_timeout_ms)
            except Error as err:
                log.warning("load_state_wait_failed_proceeding %s", str(err))
            return

        max_attempts = 4
        backoff_ms = [2000, 4000, 8000]
        last_error: Error | None = None
        for attempt in range(max_attempts):
            try:
                page.goto(
                    CHAT_URL,
                    wait_until="commit",
                    timeout=navigation_timeout_ms,
                )
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=load_timeout_ms)
                except Error as err:
                    log.warning("load_state_wait_failed_proceeding %s", str(err))
                return
            except Error as err:
                last_error = err
                if attempt < max_attempts - 1:
                    wait = backoff_ms[attempt] if attempt < len(backoff_ms) else 8000
                    log.warning(
                        "page_goto_failed_retrying %s %s %s %s", attempt + 1, max_attempts, str(err), wait // 1000
                    )
                    page.wait_for_timeout(wait)
        if last_error is not None:
            raise last_error

    def _start_new_chat(self, page: Page, opt_in: bool = True) -> None:
        """Start a clean Qwen conversation so stale cards cannot affect monitoring."""
        if not opt_in:
            return
        try:
            if "/c/" in page.url.lower():
                log.info("active_chat_thread_detected_navigating %s", page.url)
                self._goto_chat(page, 15_000, NAVIGATION_LOAD_TIMEOUT_MS)
                page.wait_for_timeout(1000)

            if click_first_visible_enabled(page, NEW_CHAT_SELECTORS, timeout_ms=3000):
                page.wait_for_timeout(800)
                with contextlib.suppress(Error, TimeoutError):
                    page.wait_for_selector("textarea.message-input-textarea, textarea", state="visible", timeout=3000)
                log.debug("Started a clean Qwen chat before dispatch")
        except Error as exc:
            log.debug("new_chat_reset_unavailable %s", str(exc))

    @contextmanager
    def _open_chat_page_standalone(self, cfg: AppConfig) -> Iterator[Page]:
        """Standalone launch fallback used when no lifecycle is injected.

        Mirrors ``BrowserLifecycle._open_chat_page`` without the tenacity
        retry loop: a single launch attempt, used only in standalone
        test harnesses where the full lifecycle view is not available.
        """
        from playwright.sync_api import sync_playwright

        session_dir = cfg.session_path
        kwargs: dict[str, Any] = {
            "user_data_dir": str(session_dir),
            "channel": None,
            "headless": bool(getattr(cfg, "headless", False)),
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-session-crashed-bubble",
                "--disable-infobars",
            ],
            "viewport": {"width": 1280, "height": 800},
        }
        if getattr(cfg, "disable_sandbox", False):
            kwargs["args"].append("--no-sandbox")
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(**kwargs)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                self.open_chat_page(page, strict=False)
                yield page
            finally:
                ctx.close()

    def __repr__(self) -> str:
        """Return string representation of BrowserNavigation."""
        return "BrowserNavigation()"


__all__ = ["BrowserNavigation"]
