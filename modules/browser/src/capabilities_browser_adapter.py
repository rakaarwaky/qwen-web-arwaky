"""Browser lifecycle capability (Playwright adaptation).

Capabilities layer: implements IBrowserProtocol. Imports taxonomy, contract(protocol),
utility only. Logger obtained via get_logger (standard library), not via another capability.
"""

from __future__ import annotations

import contextlib
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

from modules.shared.src.browser.contract_browser_protocol import (
    IBrowserModelPolicyProtocol,
    IBrowserProtocol,
)
from modules.shared.src.browser.utility_browser_async_loop import isolate_thread_event_loop
from modules.shared.src.browser.utility_browser_model_target import bind_target_model, target_model
from modules.shared.src.browser.utility_browser_session_check import (
    _in_page_expiry_banner_visible,
    assert_on_chat_page,
    session_is_alive,
)
from modules.shared.src.common.taxonomy_core_constant import (
    CHAT_URL,
    LAUNCH_RETRY_WAIT_SEC,
    NAVIGATION_LOAD_TIMEOUT_MS,
    NAVIGATION_TIMEOUT_MS,
    NEW_CHAT_SELECTORS,
    TEXTAREA_SELECTOR,
)
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import (
    AuthRequiredError,
    BrowserLaunchError,
)
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_NETWORK_RECONNECTING,
    EVENT_SESSION_EXPIRED,
    EVENT_WEB_LOADED,
)
from modules.shared.src.common.taxonomy_core_vo import ModelLabel, WaitTimeoutMs
from modules.shared.src.common.utility_dom_helper import click_first_visible_enabled
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.session.utility_session_cloner import clean_stale_locks
from modules.shared.src.update.utility_update_browser_binary import find_chrome_binary, is_headless_shell_binary

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


class BrowserAdapter(
    IBrowserProtocol,
):
    """Persistent Chromium browser context adapter implementing the browser contract."""

    def __init__(self, model_policy: IBrowserModelPolicyProtocol) -> None:
        """Initialize BrowserAdapter.

        *model_policy* is the injected model-policy capability that owns the
        issue #283/#374 model selection/verification fallback rules. The
        composition root (`modules/root_core_container.py`) constructs
        `BrowserModelPolicy` and injects the same instance into the adapter
        and the container, so both views see one shared seam. The adapter
        file itself never imports a sibling capability (AES201); the public
        seam stays the 2-method `IBrowserModelPolicyProtocol`, and the
        adapter reaches the DOM-mechanic internals through the concrete
        `BrowserModelPolicy` type.
        """
        self._model_policy = model_policy

    # Block 2: Public Contract

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
            self._wait_for_model_picker_ready(page)

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
        # it manually. The model-policy capability owns the fallback rules;
        # the adapter binds the run target so the picker helpers read the
        # right model.
        target = target_model()
        bind_target_model(target)
        switched = self.ensure_default_model(page)

        # Step 6: Verify the switch actually happened. A readable but different
        # model degrades to the first available picker entry with a WARNING
        # (issue #283 AC-2) instead of aborting, and the event carries
        # ``fallback=True`` so the substitution is auditable (issue #374).
        verified, detected = self._verify_default_model(page, require_switch=switched)
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": detected, "fallback": not verified})

    def select_model(self, page: Page, emitter: LifecycleEmitter) -> ModelLabel:
        """Read/select the default model on *page*; return the chosen label.

        Delegates to the model-policy capability (issue #283/#374 fallback
        rules).
        """
        return self._model_policy.select_model(page, emitter)

    def verify_model(self, page: Page, expected: ModelLabel) -> bool:
        """Return True when *page* shows *expected* as the active model.

        Delegates to the model-policy capability.
        """
        return self._model_policy.verify_model(page, expected)

    def verify_default_model(
        self, page: Page, target: ModelLabel, require_switch: bool = True
    ) -> tuple[bool, ModelLabel]:
        """Confirm the active model is *target*, degrading when it is not.

        Delegates to the model-policy capability.
        """
        return self._model_policy.verify_default_model(page, target, require_switch)

    def select_first_available_model(self, page: Page) -> ModelLabel | None:
        """Select the first model the picker offers, or return None when unreadable.

        Delegates to the model-policy capability.
        """
        return self._model_policy.select_first_available_model(page)

    def wait_for_picker_ready(self, page: Page, timeout_ms: WaitTimeoutMs = WaitTimeoutMs(15_000)) -> None:
        """Wait until the hydrated picker exposes the configured default option.

        Delegates to the model-policy capability.
        """
        self._model_policy.wait_for_picker_ready(page, timeout_ms)

    def retry_default_model_selection(self, page: Page) -> None:
        """Close a stale picker, allow hydration, and retry default-model selection.

        Delegates to the model-policy capability.
        """
        self._model_policy.retry_default_model_selection(page)

    def get_model_trigger(self, page: Page) -> Any:
        """Return locator for active model selector trigger button/div.

        Delegates to the model-policy capability.
        """
        return self._model_policy.get_model_trigger(page)

    def try_set_as_default(self, page: Page) -> None:
        """Best-effort attempt to click 'Set default' in Qwen UI picker.

        Delegates to the model-policy capability.
        """
        self._model_policy.try_set_as_default(page)

    def _verify_default_model(self, page: Page, require_switch: bool = True) -> tuple[bool, str]:
        """Confirm the active model is the configured default, degrading when it is not.

        Delegates to the model-policy capability (issue #283/#374 fallback
        rules).
        """
        target = target_model()
        verified, detected = self._model_policy.verify_default_model(page, target, require_switch)
        return verified, str(detected)

    def _select_first_available_model(self, page: Page) -> str | None:
        """Select the first model the picker offers, or return None when unreadable.

        Delegates to the model-policy capability.
        """
        result = self._model_policy.select_first_available_model(page)
        return None if result is None else str(result)

    def _wait_for_model_picker_ready(self, page: Page, timeout_ms: int = 15_000) -> None:
        """Wait until the hydrated picker exposes the configured default option.

        Delegates to the model-policy capability.
        """
        self._model_policy.wait_for_picker_ready(page, WaitTimeoutMs(timeout_ms))

    def _retry_default_model_selection(self, page: Page) -> None:
        """Close a stale picker, allow hydration, and retry default-model selection.

        Delegates to the model-policy capability.
        """
        self._model_policy.retry_default_model_selection(page)

    def _get_model_trigger(self, page: Page) -> Any:
        """Return locator for active model selector trigger button/div.

        Delegates to the model-policy capability.
        """
        return self._model_policy.get_model_trigger(page)

    def ensure_default_model(self, page: Page) -> bool:
        """Best-effort: ensure the active Qwen model is the configured default.

        Delegates to the model-policy capability.
        """
        return self._model_policy.ensure_default_model(page)

    def _try_set_as_default(self, page: Page) -> None:
        """Best-effort attempt to click 'Set default' or 'Set as default' in Qwen UI picker.

        Delegates to the model-policy capability.
        """
        self._model_policy.try_set_as_default(page)

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
        assert_on_chat_page(page)

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
            assert_on_chat_page(page)
            return session_is_alive(page)
        except AuthRequiredError:
            return False
        except Error as exc:
            log.warning("session_validation_failed %s", str(exc))
            return False

    def detect_session_expired(self, page: Page) -> bool:
        """True when the live page now shows an in-page session-expiry notice.

        Re-runs the banner text/selector scan from ``_assert_on_chat_page``
        against the CURRENT page state. Best-effort: a DOM that is unreadable
        (mid-hydration) is not a signal, so the method returns False rather
        than raising. Used by prompt pipelines after a failed dispatch to
        surface ``EVENT_SESSION_EXPIRED``.
        """
        return _in_page_expiry_banner_visible(page)

    def renew_session(self, cfg: Any, session_path: Path | None = None, executable_path: str | None = None) -> None:
        """Attempt to renew the session credentials on *cfg*'s master profile in place.

        Opens the chat page on the master profile (login mode, no ephemeral
        clone) so that when the ``auth-session`` cookie has expired but the
        long-lived ``refresh_token`` is still valid, the site's own JS can
        exchange the refresh token for a fresh session cookie while the page
        loads. The renewed cookies are persisted to the master profile on
        context close.

        ``session_path`` overrides the profile directory when provided;
        ``executable_path`` is the Chromium binary to launch (injected by
        the update module); both default to ``None`` (resolve from *cfg*).

        Raises:
            AuthRequiredError: When the session could not be renewed — either
                the page still lands on a login/guest view, shows a login
                form, or the refresh token itself is dead (manual re-login
                is the only path left).
        """
        del session_path, executable_path
        # Login mode: create_ephemeral_session yields the master path directly,
        # so any cookie the browser writes persists to the master profile.
        with self._open_chat_page(cfg, _mode="login", strict_auth=True):
            pass

    @contextmanager
    def open_login_page(self, cfg: Any) -> Iterator[Page]:
        """Open one fresh page on ``cfg``'s profile and go to the chat URL.

        Thin wrapper over ``browser_session`` + first page + ``goto``.
        Used by the manual login window flow; performs no model selection.
        No auth assertion: the page is handed to the operator to log in.
        """
        with self.browser_session(cfg) as ctx:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            self._goto_chat(page, NAVIGATION_TIMEOUT_MS, NAVIGATION_LOAD_TIMEOUT_MS)
            yield page

    def wire_diagnostics(self, ctx: BrowserContext) -> None:
        """Attach all diagnostics to *ctx*: the context-level asset-abort
        route, the page-creation hook, URL scrubbing, and third-party noise
        demotion. Called once per context from `browser_session` (or the
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

    @contextmanager
    def health_probe_page(
        self, cfg: Any, session_path: Path | None = None, executable_path: str | None = None
    ) -> Iterator[Page]:
        """Open one ready, authenticated chat page on ``cfg``'s session profile.

        Mirrors the navigation half of ``browser_session`` (fresh ephemeral
        profile copy, asset blocking, eager chat navigation, auth assert)
        but stops before model selection and prompt dispatch, so a health
        probe pays only the page-load cost. Yields the live page; the
        context exit tears down the browser process group.

        Raises:
            AuthRequiredError: When the page lands on a login or guest
                view, or shows a login form.
        """
        del session_path, executable_path
        with self._open_chat_page(cfg, _mode="", strict_auth=False) as page:
            yield page

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

    @contextmanager
    def _open_chat_page(
        self,
        cfg: Any,
        *,
        _mode: str,
        strict_auth: bool,
        session_path: Path | None = None,
    ) -> Iterator[Page]:
        """The shared launch → navigate → auth-assert sequence for one profile.

        ``renew_session`` and ``health_probe_page`` are the only two callers
        that needed exactly this: an ephemeral profile clone (or the master
        itself in login mode), the standard Chromium launch arguments, a fresh
        context, a chat navigation, and one authentication assertion. Keeping
        the sequence here means the launch args, the headless-shell fallback,
        and the tear-down rule live in one place instead of two.

        ``strict_auth`` mirrors the two consumers: renewal asserts on the
        chat page (strict), the health probe tolerates a page that is still
        hydrating (non-strict).

        ``session_path`` is the plain profile path prepared by the session
        `ProfilePreparer`; when omitted the adapter resolves it from
        *cfg.session_path*. The capability no longer clones the profile itself.
        """
        session_dir = session_path if session_path is not None else cfg.session_path
        kwargs = self._launch_kwargs(session_dir, cfg)
        with sync_playwright() as p:
            ctx = self._launch_context(p, kwargs)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                self._goto_chat(page, NAVIGATION_TIMEOUT_MS, NAVIGATION_LOAD_TIMEOUT_MS)
                assert_on_chat_page(page, strict=strict_auth)
                yield page
            finally:
                ctx.close()

    def _launch_kwargs(self, session_dir: Path, cfg: Any) -> dict[str, Any]:
        """Build the persistent-context launch arguments for *cfg*.

        The one place that owns the Chromium flag set, the sandbox/headless
        extras, and the headless-shell → system-Chrome fallback, so
        ``browser_session``, ``renew_session`` (via ``_open_chat_page``), and
        ``health_probe_page`` (via ``_open_chat_page``) all launch with the
        same arguments. Callers that need extras (permissions, model
        scoping) layer them onto the returned dict.
        """
        headless = bool(getattr(cfg, "headless", False))
        chrome_bin = find_chrome_binary(headless=headless)
        chrome_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-session-crashed-bubble",
            "--disable-infobars",
        ]
        if getattr(cfg, "disable_sandbox", False):
            chrome_args.append("--no-sandbox")
        if headless:
            chrome_args.extend(
                [
                    "--disable-gpu",
                    "--disable-software-compositing",
                ]
            )

        kwargs: dict[str, Any] = {
            "user_data_dir": str(session_dir),
            "channel": None,
            "headless": headless,
            "args": chrome_args,
            "viewport": {"width": 1280, "height": 800},
        }
        if chrome_bin and Path(chrome_bin).exists():
            if headless or not is_headless_shell_binary(chrome_bin):
                kwargs["executable_path"] = chrome_bin
            else:
                # Headful launch but only a headless-shell build is
                # available: drop executable_path and let Playwright use
                # the system Chrome channel so a visible window opens.
                kwargs["channel"] = "chrome"
                log.info("browser_headful_fallback_system_chrome")
        return kwargs

    def _clean_stale_locks(self, user_data_dir: str) -> None:
        """Clean up stale Chromium lock files if process crashed or before launch.

        Delegates to the shared utility so every launcher (the ephemeral
        session clone, the cloner's own sweep) removes exactly the same lock
        set — one source of truth for "what counts as a stale lock".
        """
        clean_stale_locks(Path(user_data_dir))

    def _launch_context(self, p: Playwright, kwargs: dict[str, Any]) -> BrowserContext:
        """Launch the persistent context with tenacity retry for transient crashes.

        Launch failures are logged at DEBUG rather than WARNING: a
        best-effort validation probe (``mode="session-check"``) that
        cannot launch because the browser binary is missing or crashed
        must not flood the operator log — the manual login that follows
        is the path that matters to the user.
        """
        user_data_dir = kwargs.get("user_data_dir", "")
        if user_data_dir:
            self._clean_stale_locks(user_data_dir)

        def _before_sleep(retry_state: RetryCallState) -> None:
            sleep_val = retry_state.next_action.sleep if retry_state.next_action else 2
            if user_data_dir:
                self._clean_stale_locks(user_data_dir)
            log.debug(
                "browser_launch_failed_retrying %s %s %s",
                retry_state.attempt_number,
                sleep_val,
                str(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
            )

        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_fixed(LAUNCH_RETRY_WAIT_SEC),
            before_sleep=_before_sleep,
            reraise=True,
        ):
            with attempt:
                ctx = p.chromium.launch_persistent_context(**kwargs)
                return ctx

        raise RuntimeError("browser launch failed after retries")  # pragma: no cover

    @contextmanager
    def browser_session(
        self, cfg: Any, session_path: Path | None = None, executable_path: str | None = None
    ) -> Iterator[BrowserContext]:
        """Manage persistent Chromium browser context with session caching and asset optimization.

        For login mode, connects directly to the master session profile so credentials
        are saved permanently. For prompt jobs, runs in an isolated ephemeral copy of
        the session directory so multiple jobs can execute concurrently in parallel
        (1 browser process per job) without Chromium SingletonLock conflicts.

        ``session_path`` overrides the profile directory when provided
        (a plain path prepared by the session `ProfilePreparer`); when
        omitted, the adapter resolves it from *cfg.session_path*.
        ``executable_path`` is the Chromium binary to launch (injected by
        the update module); when omitted, the adapter resolves it.
        """
        session_dir = session_path if session_path is not None else cfg.session_path
        mode = getattr(cfg, "mode", "")
        # Per-run --model override is bound exactly once, after the ephemeral
        # session launches, so concurrent Swarm legs never read each other's
        # target model (Issue #283). Non-string values (e.g. a MagicMock in
        # a test harness) are ignored so they never pollute the contextvar.

        session_dir.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            session_dir.chmod(0o700)

        kwargs = self._launch_kwargs(session_dir, cfg)
        kwargs["permissions"] = ["clipboard-read", "clipboard-write"]
        if executable_path is not None:
            kwargs["executable_path"] = executable_path

        isolate_thread_event_loop()

        context_started = False
        try:
            with sync_playwright() as p:
                ctx = self._launch_context(p, kwargs)
                context_started = True
                # Bind per-run model override after the context launches so
                # concurrent runs scope their model to this session only.
                _model = getattr(cfg, "model", "")
                bind_target_model(
                    ModelLabel(_model.strip()) if isinstance(_model, str) and _model.strip() else target_model()
                )

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

                self.wire_diagnostics(ctx)

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
    return str(target_model())


def _is_third_party_noise(url: str) -> bool:
    """Return True when *url* points at a known third-party tracking/CDN domain."""
    from urllib.parse import urlparse

    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return any(host == d or host.endswith("." + d) for d in _THIRD_PARTY_NOISE_HOSTS)
