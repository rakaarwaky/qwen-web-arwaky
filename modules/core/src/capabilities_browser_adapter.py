"""Browser lifecycle capability (Playwright adaptation).

Capabilities layer: implements IBrowserProtocol. Imports taxonomy, contract(protocol),
utility only. Logger obtained via get_logger (standard library), not via another capability.
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    BrowserContext,
    Error,
    Page,
    Playwright,
    sync_playwright,
)
from tenacity import RetryCallState, Retrying, stop_after_attempt, wait_fixed

from modules.core.src.utility_core_async_loop import isolate_thread_event_loop
from modules.core.src.utility_core_browser_binary import find_chrome_binary
from modules.core.src.utility_core_dom_helper import click_first_visible_enabled, is_any_visible
from modules.core.src.utility_core_logger_factory import get_logger
from modules.core.src.utility_core_session_cloner import create_ephemeral_session
from modules.shared.src.contract_core_protocol import IBrowserProtocol
from modules.shared.src.taxonomy_core_constant import (
    AUTH_KEYWORDS,
    CHAT_URL,
    DEFAULT_MODEL,
    LOGIN_FORM_SELECTORS,
    MODEL_SELECTOR_BUTTON,
    NAVIGATION_LOAD_TIMEOUT_MS,
    NAVIGATION_TIMEOUT_MS,
    NEW_CHAT_SELECTORS,
    TEXTAREA_SELECTOR,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_error import (
    AuthRequiredError,
    BrowserLaunchError,
    ModelSwitchError,
)
from modules.shared.src.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_NETWORK_RECONNECTING,
    EVENT_WEB_LOADED,
)

log = get_logger("browser")

# Issue #283: the targeted model is per-run configuration. A contextvars token
# lets concurrent runs (Swarm fan-out, parallel jobs) keep their own override
# without mutating shared state. The override is active only for runs that
# received an AppConfig with a non-empty ``model`` field; the constant-level
# default (QWEN_DEFAULT_MODEL / QWEN_MODEL env var) is preserved otherwise.
_TARGET_MODEL: contextvars.ContextVar[str] = contextvars.ContextVar("qwa_target_model", default=DEFAULT_MODEL)


def _active_model() -> str:
    """Return the model a running pipeline should target.

    ``ContextVar.get()`` returns the raw stored value, which in tests may be a
    ``MagicMock`` (leaked by a prior unmocked ``browser_session`` call). Only a
    genuine string is a valid target; anything else falls back to the default.
    """
    value = _TARGET_MODEL.get()
    if isinstance(value, str) and value:
        return value
    return DEFAULT_MODEL


# Block 1: Class Definition & Constructor


class SessionCheck:
    """Validates that the browser session and Qwen chat UI are alive."""

    def __init__(self, page: Page) -> None:
        """Initialize with a Playwright Page instance."""
        self.page = page

    # ─── Block 2: Public Contract (IBrowserProtocol ONLY) ──

    def is_alive(self) -> bool:
        """Return True if the session is stable and the chat UI is responsive."""
        try:
            ready = self.page.evaluate("() => document.readyState")
            if ready != "complete":
                log.warning("session_check_failed %s %s", "page_not_ready", ready)
                return False

            if not self.page.query_selector(TEXTAREA_SELECTOR):
                log.warning("session_check_failed %s", "textarea_missing")
                return False

            return True
        except Error as exc:
            log.warning("session_check_failed %s %s", "playwright_error", str(exc))
            return False
        except Exception as exc:  # defensive fallback beyond playwright Error
            log.warning("session_check_failed %s %s", "unexpected_error", str(exc))
            return False

    def check_auth(self) -> None:
        """Raise AuthRequiredError if the session is no longer authenticated or UI is missing."""
        try:
            _assert_on_chat_page(self.page)
        except AuthRequiredError:
            raise
        except Error as exc:
            raise AuthRequiredError(f"Session invalid (browser error): {exc}") from exc

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of SessionCheck."""
        return f"SessionCheck(page={self.page!r})"


def _assert_on_chat_page(page: Page) -> None:
    """Raise AuthRequiredError if the page is a login/auth/guest page (URL + DOM check)."""
    current_url = page.url.lower()

    if any(k in current_url for k in AUTH_KEYWORDS):
        raise AuthRequiredError(
            f"Not authenticated — browser is on login or guest page ({page.url}). "
            "Please run 'qwen-web-arwaky --login' or click Login in TUI to authenticate first."
        )

    combined_login = ", ".join(LOGIN_FORM_SELECTORS)
    if is_any_visible(page, combined_login):
        raise AuthRequiredError(
            f"Not authenticated — login form/button detected on page ({page.url}). "
            "Please run 'qwen-web-arwaky --login' or click Login in TUI to authenticate first."
        )

    if not page.query_selector(TEXTAREA_SELECTOR):
        log.warning("chat_textarea_missing_but_no_login_form_detected %s", page.url)


# Block 1: Class Definition & Constructor


class BrowserAdapter(IBrowserProtocol):
    """Persistent Chromium browser context adapter implementing the browser contract."""

    def __init__(self) -> None:
        """Initialize BrowserAdapter."""
        pass

    # Block 2: Public Contract

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

    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset the page to a clean state by navigating back to chat.qwen.ai."""
        try:
            emitter.emit(EVENT_NETWORK_RECONNECTING, {"url": CHAT_URL})
            self._goto_chat(page, 10_000, NAVIGATION_LOAD_TIMEOUT_MS)
        except Error as e:
            log.warning("page_reset_failed %s", str(e))

    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate to chat.qwen.ai, verify session, and emit lifecycle events step-by-step:

        Step 1: Navigate to chat page
        Step 2: Assert authentication session
        Step 3: Start clean conversation state
        Step 4: Emit lifecycle events (EVENT_WEB_LOADED, EVENT_LOGIN_VERIFIED)
        Step 5: Select the configured default model (issue #283)
        Step 6: Verify the model is active; when the configured model is not
        offered by the picker, fall back to the first available model and log a
        WARNING instead of aborting the pipeline, marking the event
        ``fallback=True`` whenever a different model is read and aborting only
        when no model label can be read at all
        """
        # Step 1: Navigate to chat URL
        self._goto_chat(page, NAVIGATION_TIMEOUT_MS, NAVIGATION_LOAD_TIMEOUT_MS)

        # Step 2: Verify user authentication
        _assert_on_chat_page(page)

        # Step 3: Start clean conversation state. Qwen hydrates the model picker
        # asynchronously after this reset; wait for its actual default option rather
        # than sleeping for a fixed duration.
        self._start_new_chat(page)
        with contextlib.suppress(Error):
            self._wait_for_model_picker_ready(page)

        # Step 4: Emit lifecycle events
        emitter.emit(EVENT_WEB_LOADED, {"url": page.url})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": page.url})

        # Step 5: Select the configured default model so the user never picks
        # it manually.
        switched = self.ensure_default_model(page)

        # Step 6: Verify the switch actually happened. A readable but different
        # model degrades to the first available picker entry with a WARNING
        # (issue #283 AC-2) instead of aborting, and the event carries
        # ``fallback=True`` so the substitution is auditable (issue #374).
        verified, detected = self._verify_default_model(page, require_switch=switched)
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": detected, "fallback": not verified})

    def _verify_default_model(self, page: Page, require_switch: bool = True) -> tuple[bool, str]:
        """Confirm the active model is the configured default, degrading when it is not.

        Runs after ``ensure_default_model`` so a silent picker failure cannot let
        the pipeline dispatch the prompt to an unrecorded model. Returns
        ``(True, target)`` when the configured default is active. When the
        configured model is absent from the picker, the first available model is
        selected and a WARNING is logged (issue #283 AC-2); the method then
        returns ``(False, fallback)`` so the caller can proceed with the active
        model instead of aborting the pipeline (issue #374). Raises
        ``ModelSwitchError`` only when no model label can be read at all, since
        the active model is then unknowable. When the best-effort switch reported
        failure (``require_switch=False``), verification is retried while the
        model picker hydrates so a slow picker cannot fail the pipeline.
        """
        # Model picker options can arrive after the committed page document,
        # especially when Qwen's static assets are slow. Keep this readiness gate
        # bounded and retry selection instead of failing the whole pipeline on the
        # first stale model label.
        attempts = 5
        current = ""
        target = _active_model()
        for attempt in range(attempts):
            try:
                picker = self._get_model_trigger(page)
                picker.wait_for(state="visible", timeout=5000)
                current = (picker.inner_text() or "").replace("\n", " ").strip()
            except Error as exc:
                if attempt + 1 < attempts:
                    log.debug("verify_default_model_read_retry %s %s %s", target, str(exc), attempt + 1)
                    self._retry_default_model_selection(page)
                    continue
                fallback = self._select_first_available_model(page)
                if fallback is not None:
                    return False, fallback
                raise ModelSwitchError(
                    f"Cannot read active model from '{MODEL_SELECTOR_BUTTON}' button: {exc}"
                ) from exc
            if target in current.split():
                log.debug("verify_default_model_ok %s", target)
                return True, target
            if attempt + 1 < attempts:
                log.debug("verify_default_model_retry %s %s %s %s", target, current, require_switch, attempt + 1)
                self._retry_default_model_selection(page)
                continue
            # FRD FR-001 fallback: the configured default is absent from the
            # picker, so pipeline availability wins over exact matching
            # (issue #374). Prefer actively selecting the first available model
            # so the run continues on a known-good picker entry (issue #283).
            fallback = self._select_first_available_model(page)
            if fallback is not None:
                return False, fallback
            log.warning(
                "default_model_unavailable_proceeding_with_active %s %s",
                target,
                current,
            )
            return False, current
        fallback = self._select_first_available_model(page)
        if fallback is not None:
            return False, fallback
        raise ModelSwitchError(f"Default model not active: expected '{target}'")

    def _select_first_available_model(self, page: Page) -> str | None:
        """Select the first model the picker offers, or return None when unreadable.

        The graceful-degradation path for a renamed or deprecated model
        identifier (issue #283 AC-2): the run continues on whatever model the
        picker exposes first, and the WARNING names both the configured and the
        active model so the discrepancy is auditable.
        """
        try:
            picker = self._get_model_trigger(page)
            picker.click(timeout=5000)
            try:
                first_option = page.locator(".wms-list__item").first
                if first_option.is_visible(timeout=2000) is not True:
                    return None
                label = (first_option.inner_text() or "").replace("\n", " ").strip()
                first_option.click(timeout=5000)
            finally:
                with contextlib.suppress(Error):
                    page.keyboard.press("Escape")
        except Error as exc:
            log.warning("model_fallback_unavailable %s %s", _active_model(), str(exc))
            return None
        if not label:
            return None
        log.warning(
            "model_fallback_activated %s %s %s",
            _active_model(),
            label,
            "configured model not offered by the model picker",
        )
        return label

    def _wait_for_model_picker_ready(self, page: Page, timeout_ms: int = 15_000) -> None:
        """Wait until the hydrated picker exposes the configured default option."""
        target = _active_model()
        picker = self._get_model_trigger(page)
        picker.wait_for(state="visible", timeout=timeout_ms)
        picker.click(timeout=5000)
        try:
            option: Any = page.get_by_role("option", name=target)
            with contextlib.suppress(Error):
                loc = page.locator(".wms-list__item", has_text=target).first
                if loc.is_visible(timeout=1000) is True:
                    option = loc
            option.wait_for(state="visible", timeout=timeout_ms)
        finally:
            with contextlib.suppress(Error):
                page.keyboard.press("Escape")

    def _retry_default_model_selection(self, page: Page) -> None:
        """Close a stale picker, allow hydration, and retry default-model selection."""
        with contextlib.suppress(Error):
            page.keyboard.press("Escape")
            page.wait_for_timeout(2000)
        self.ensure_default_model(page)

    def _get_model_trigger(self, page: Page) -> Any:
        """Return locator for active model selector trigger button/div."""
        with contextlib.suppress(Error):
            trigger = page.locator(".wms-trigger, [aria-label='Select Model']").first
            if trigger.is_visible(timeout=1000) is True:
                return trigger
        return page.get_by_role("button", name=MODEL_SELECTOR_BUTTON)

    def ensure_default_model(self, page: Page) -> bool:
        """Best-effort: ensure the active Qwen model is the configured default.

        Opens the model picker only long enough to click the default option. The
        call is defensive — any failure is logged and swallowed so it can never
        block the prompt pipeline (the verify step then drives fallback).
        """
        target = _active_model()
        try:
            picker = self._get_model_trigger(page)
            picker.wait_for(state="visible", timeout=5000)
            picker.click(timeout=5000)

            # Option item (.wms-list__item or role=option)
            option = page.get_by_role("option", name=target)
            with contextlib.suppress(Error):
                loc = page.locator(".wms-list__item", has_text=target).first
                if loc.is_visible(timeout=1000) is True:
                    option = loc

            option.wait_for(state="visible", timeout=5000)
            option.click(timeout=5000)
            page.wait_for_timeout(300)

            self._try_set_as_default(page)
            log.debug("ensure_default_model_applied %s", target)
            return True
        except Error as exc:
            log.debug("ensure_default_model_skipped %s %s", target, str(exc))
            return False

    def _try_set_as_default(self, page: Page) -> None:
        """Best-effort attempt to click 'Set default' or 'Set as default' in Qwen UI picker."""
        try:
            picker = self._get_model_trigger(page)
            picker.click(timeout=3000)
            page.wait_for_timeout(300)

            with contextlib.suppress(Error):
                item = page.locator(".wms-list__item", has_text=DEFAULT_MODEL).first
                if item.is_visible(timeout=1500) is True:
                    pin = item.locator(".wms-list__pin-action, :has-text('Set as default')").first
                    if "Set as default" in (pin.inner_text() or ""):
                        pin.evaluate("e => e.click()")
                        log.debug("set_default_model_ui_applied %s", _active_model())
                        page.wait_for_timeout(300)

            with contextlib.suppress(Error):
                page.keyboard.press("Escape")
        except Error as exc:
            log.debug("set_default_model_ui_skipped %s", str(exc))
            with contextlib.suppress(Error):
                page.keyboard.press("Escape")

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

    def check_auth(self, page: Page) -> None:
        """Raise AuthRequiredError if the page is on a login/auth URL or login form detected."""
        _assert_on_chat_page(page)

    def check_session(self, page: Page) -> bool:
        """Return True only when an authenticated chat page is ready for use.

        ``check_auth`` intentionally tolerates a page that is still loading and
        has not exposed its login form yet. Manual login needs a stronger,
        boolean check after the user finishes, so this method combines the URL
        and login-form check with the live chat-input check.
        """
        try:
            try:
                page.wait_for_load_state("load", timeout=15_000)
            except Error:
                # A partially loaded page can still expose the authenticated UI;
                # SessionCheck below is the final source of truth.
                log.debug("session_load_state_wait_failed")
            _assert_on_chat_page(page)
            return SessionCheck(page).is_alive()
        except AuthRequiredError:
            return False
        except Error as exc:
            log.warning("session_validation_failed %s", str(exc))
            return False
        except Exception as exc:  # defensive fallback for closed pages/adapters
            log.warning("session_validation_failed %s", str(exc))
            return False

    def _clean_stale_locks(self, user_data_dir: str) -> None:
        """Clean up stale Chromium lock files if process crashed or before launch."""
        session_path = Path(user_data_dir)
        for fname in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_path = session_path / fname
            try:
                if lock_path.is_symlink() or lock_path.exists():
                    lock_path.unlink(missing_ok=True)
            except OSError as e:
                log.warning("stale_lock_delete_failed %s %s", lock_path, str(e))

    def _launch_context(self, p: Playwright, kwargs: dict[str, Any]) -> BrowserContext:
        """Launch the persistent context with tenacity retry for transient crashes."""
        user_data_dir = kwargs.get("user_data_dir", "")
        if user_data_dir:
            self._clean_stale_locks(user_data_dir)

        def _before_sleep(retry_state: RetryCallState) -> None:
            sleep_val = retry_state.next_action.sleep if retry_state.next_action else 2
            if user_data_dir:
                self._clean_stale_locks(user_data_dir)
            log.warning(
                "browser_launch_failed_retrying %s %s %s",
                retry_state.attempt_number,
                sleep_val,
                str(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
            )

        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_fixed(2),
            before_sleep=_before_sleep,
            reraise=True,
        ):
            with attempt:
                ctx = p.chromium.launch_persistent_context(**kwargs)
                return ctx

        raise RuntimeError("browser launch failed after retries")  # pragma: no cover

    @contextmanager
    def browser_session(self, cfg: Any) -> Iterator[BrowserContext]:
        """Manage persistent Chromium browser context with session caching and asset optimization.

        For login mode, connects directly to the master session profile so credentials
        are saved permanently. For prompt jobs, runs in an isolated ephemeral copy of
        the session directory so multiple jobs can execute concurrently in parallel
        (1 browser process per job) without Chromium SingletonLock conflicts.
        """
        master_session = cfg.session_path
        mode = getattr(cfg, "mode", "")
        # Issue #283: scope any per-run --model override to this session so
        # concurrent runs do not read each other's target model. The default
        # (empty string) resolves back to the constant so unchanged runs keep
        # their previous behavior. Non-string values (e.g. a MagicMock in a
        # test harness) are ignored so they never pollute the contextvar.
        override = getattr(cfg, "model", "")
        if isinstance(override, str) and override.strip():
            _TARGET_MODEL.set(override.strip())

        with create_ephemeral_session(master_session, mode=mode) as session_dir:
            chrome_bin = find_chrome_binary()

            chrome_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-session-crashed-bubble",
                "--disable-infobars",
            ]
            if cfg.disable_sandbox:
                chrome_args.append("--no-sandbox")

            if cfg.headless:
                chrome_args.extend(
                    [
                        "--disable-gpu",
                        "--disable-software-compositing",
                    ]
                )

            kwargs: dict[str, Any] = {
                "user_data_dir": str(session_dir),
                "headless": cfg.headless,
                "permissions": ["clipboard-read", "clipboard-write"],
                "args": chrome_args,
                "viewport": {"width": 1280, "height": 800},
            }

            if chrome_bin and Path(chrome_bin).exists():
                kwargs["executable_path"] = chrome_bin

            isolate_thread_event_loop()

            context_started = False
            try:
                with sync_playwright() as p:
                    ctx = self._launch_context(p, kwargs)
                    context_started = True
                    # Issue #283: bind per-run model override so the browser
                    # adapter references the correct token across all nested
                    # helpers without threading an extra parameter.
                    _TARGET_MODEL.set(cfg.model or DEFAULT_MODEL)

                    # Eagerly navigate the initial about:blank page to CHAT_URL
                    # so the browser starts loading while route/diagnostics setup
                    # and orchestrator init happen in parallel.
                    if ctx.pages:
                        try:
                            ctx.pages[0].goto(
                                CHAT_URL,
                                wait_until="commit",
                                timeout=NAVIGATION_TIMEOUT_MS,
                            )
                            log.debug("browser_eager_navigate_ok %s", CHAT_URL)
                        except Error as exc:
                            log.warning("browser_eager_navigate_failed_retry_in_navigate %s", str(exc))

                    if mode != "login":
                        ctx.route(
                            "**/*.{png,jpg,jpeg,gif,webp,mp4,mp3,woff,woff2,ttf,otf}",
                            lambda r: r.abort(),
                        )

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
                            log.warning("browser_request_failed %s %s", _sanitize_url(request.url), request.failure)

                        def on_console(message: Any) -> None:
                            """Log page console errors and warnings."""
                            if message.type in {"error", "warning"}:
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
                                log.warning("browser_http_error %s %s", response.status, _sanitize_url(response.url))
                            elif response.request.method in {"POST", "PUT", "PATCH"} and "qwen.ai" in url:
                                log.info(
                                    "browser_mutation_response %s %s", response.status, _sanitize_url(response.url)
                                )

                        page.on("request", on_request)
                        page.on("requestfailed", on_request_failed)
                        page.on("console", on_console)
                        page.on("response", on_response)

                    for existing_page in ctx.pages:
                        attach_page_diagnostics(existing_page)
                    ctx.on("page", attach_page_diagnostics)
                    try:
                        yield ctx
                    finally:
                        try:
                            ctx.close()
                        except Exception as e:
                            # Teardown is best-effort and must never mask the domain failure.
                            log.warning("browser_context_cleanup_failed %s", str(e))
            except AuthRequiredError:
                raise
            except BrowserLaunchError:
                raise
            except Exception as e:
                if context_started:
                    raise
                log.critical("browser_launch_failed %s", str(e))
                raise BrowserLaunchError(f"Failed to launch browser: {e}") from e

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of BrowserAdapter."""
        return "BrowserAdapter()"
