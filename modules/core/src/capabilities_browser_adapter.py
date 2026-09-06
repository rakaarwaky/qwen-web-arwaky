"""Browser lifecycle capability (Playwright adaptation).

Capabilities layer: implements IBrowserProtocol. Imports taxonomy, contract(protocol),
utility only. Logger obtained via structlog (external), not via another capability.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import structlog
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
from modules.shared.src.contract_core_protocol import IBrowserProtocol
from modules.shared.src.taxonomy_core_constant import (
    AUTH_KEYWORDS,
    CHAT_URL,
    DEFAULT_MODEL,
    LOGIN_FORM_SELECTORS,
    MODEL_SELECTOR_BUTTON,
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

log = structlog.get_logger("browser")

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
                log.warning("session_check_failed", reason="page_not_ready", ready=ready)
                return False

            if not self.page.query_selector(TEXTAREA_SELECTOR):
                log.warning("session_check_failed", reason="textarea_missing")
                return False

            return True
        except Error as exc:
            log.warning("session_check_failed", reason="playwright_error", error=str(exc))
            return False
        except Exception as exc:  # defensive fallback beyond playwright Error
            log.warning("session_check_failed", reason="unexpected_error", error=str(exc))
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
            "Please run 'qwen-web-cli --login' or click Login in TUI to authenticate first."
        )

    combined_login = ", ".join(LOGIN_FORM_SELECTORS)
    if is_any_visible(page, combined_login):
        raise AuthRequiredError(
            f"Not authenticated — login form/button detected on page ({page.url}). "
            "Please run 'qwen-web-cli --login' or click Login in TUI to authenticate first."
        )

    if not page.query_selector(TEXTAREA_SELECTOR):
        log.warning("chat_textarea_missing_but_no_login_form_detected", url=page.url)


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
        the later DOMContentLoaded wait as best-effort. A second commit attempt
        remains available for transient connection failures.
        """
        last_error: Error | None = None
        for attempt in range(2):
            try:
                page.goto(
                    CHAT_URL,
                    wait_until="commit",
                    timeout=navigation_timeout_ms,
                )
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=load_timeout_ms)
                except Error as err:
                    log.warning("Load state wait failed, proceeding: %s", err)
                return
            except Error as err:
                last_error = err
                if attempt == 0:
                    log.warning("Initial page.goto failed (%s), retrying commit navigation...", err)
                    page.wait_for_timeout(1500)
        if last_error is not None:
            raise last_error

    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset the page to a clean state by navigating back to chat.qwen.ai."""
        try:
            emitter.emit(EVENT_NETWORK_RECONNECTING, {"url": CHAT_URL})
            self._goto_chat(page, 10_000, 15_000)
        except Error as e:
            log.warning("Failed to reset page: %s", e)

    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate to chat.qwen.ai, verify session, and emit lifecycle events step-by-step:

        Step 1: Navigate to chat page
        Step 2: Assert authentication session
        Step 3: Start clean conversation state
        Step 4: Emit lifecycle events (EVENT_WEB_LOADED, EVENT_LOGIN_VERIFIED)
        Step 5: Force the hardcoded default model (Qwen3.8-Max)
        Step 6: Verify the default model is active (abort pipeline if not)
        """
        # Step 1: Navigate to chat URL
        self._goto_chat(page, 30_000, 15_000)

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

        # Step 5: Force the hardcoded default model so the user never picks it manually.
        switched = self.ensure_default_model(page)

        # Step 6: Verify the switch actually happened; abort before prompt if not.
        self._verify_default_model(page, require_switch=switched)
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": DEFAULT_MODEL})

    def _verify_default_model(self, page: Page, require_switch: bool = True) -> None:
        """Assert the active model equals the hardcoded default.

        Runs after ``ensure_default_model`` so a silent picker failure cannot let
        the pipeline dispatch the prompt to the wrong model. Raises
        ``ModelSwitchError`` when the switch cannot be confirmed. When the
        best-effort switch reported failure (``require_switch=False``), the
        verification is retried while the model picker hydrates so a slow picker
        cannot hard-fail the pipeline prematurely.
        """
        # Model picker options can arrive after the committed page document,
        # especially when Qwen's static assets are slow. Keep this readiness gate
        # bounded and retry selection instead of failing the whole pipeline on the
        # first stale model label.
        attempts = 5
        for attempt in range(attempts):
            try:
                picker = self._get_model_trigger(page)
                picker.wait_for(state="visible", timeout=5000)
                current = (picker.inner_text() or "").replace("\n", " ").strip()
            except Error as exc:
                if attempt + 1 < attempts:
                    log.debug(
                        "verify_default_model_read_retry",
                        model=DEFAULT_MODEL,
                        error=str(exc),
                        attempt=attempt + 1,
                    )
                    self._retry_default_model_selection(page)
                    continue
                raise ModelSwitchError(
                    f"Cannot read active model from '{MODEL_SELECTOR_BUTTON}' button: {exc}"
                ) from exc
            if DEFAULT_MODEL in current.split():
                log.debug("verify_default_model_ok", model=DEFAULT_MODEL)
                return
            if attempt + 1 < attempts:
                log.debug(
                    "verify_default_model_retry",
                    model=DEFAULT_MODEL,
                    found=current,
                    require_switch=require_switch,
                    attempt=attempt + 1,
                )
                self._retry_default_model_selection(page)
                continue
            raise ModelSwitchError(f"Default model not active: expected '{DEFAULT_MODEL}', found '{current}'")
        raise ModelSwitchError(f"Default model not active: expected '{DEFAULT_MODEL}'")

    def _wait_for_model_picker_ready(self, page: Page, timeout_ms: int = 15_000) -> None:
        """Wait until the hydrated picker exposes the configured default option."""
        picker = self._get_model_trigger(page)
        picker.wait_for(state="visible", timeout=timeout_ms)
        picker.click(timeout=5000)
        try:
            option: Any = page.get_by_role("option", name=DEFAULT_MODEL)
            with contextlib.suppress(Error):
                loc = page.locator(".wms-list__item", has_text=DEFAULT_MODEL).first
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
        """Best-effort: ensure the active Qwen model is the hardcoded default.

        Opens the model picker only long enough to click the default option. The
        call is defensive — any failure is logged and swallowed so it can never
        block the prompt pipeline.
        """
        try:
            picker = self._get_model_trigger(page)
            picker.wait_for(state="visible", timeout=5000)
            picker.click(timeout=5000)

            # Option item (.wms-list__item or role=option)
            option = page.get_by_role("option", name=DEFAULT_MODEL)
            with contextlib.suppress(Error):
                loc = page.locator(".wms-list__item", has_text=DEFAULT_MODEL).first
                if loc.is_visible(timeout=1000) is True:
                    option = loc

            option.wait_for(state="visible", timeout=5000)
            option.click(timeout=5000)
            page.wait_for_timeout(300)

            self._try_set_as_default(page)
            log.debug("ensure_default_model_applied", model=DEFAULT_MODEL)
            return True
        except Error as exc:
            log.debug("ensure_default_model_skipped", model=DEFAULT_MODEL, error=str(exc))
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
                        log.debug("set_default_model_ui_applied", model=DEFAULT_MODEL)
                        page.wait_for_timeout(300)

            with contextlib.suppress(Error):
                page.keyboard.press("Escape")
        except Error as exc:
            log.debug("set_default_model_ui_skipped", error=str(exc))
            with contextlib.suppress(Error):
                page.keyboard.press("Escape")

    def _start_new_chat(self, page: Page, opt_in: bool = True) -> None:
        """Start a clean Qwen conversation so stale cards cannot affect monitoring."""
        if not opt_in:
            return
        try:
            if "/c/" in page.url.lower():
                log.info("Active chat thread detected (%s). Navigating to root chat URL...", page.url)
                self._goto_chat(page, 15_000, 15_000)
                page.wait_for_timeout(1000)

            if click_first_visible_enabled(page, NEW_CHAT_SELECTORS, timeout_ms=3000):
                page.wait_for_timeout(800)
                with contextlib.suppress(Error, TimeoutError):
                    page.wait_for_selector("textarea.message-input-textarea, textarea", state="visible", timeout=3000)
                log.debug("Started a clean Qwen chat before dispatch")
        except Error as exc:
            log.debug("New Chat reset unavailable; continuing with current chat: %s", exc)

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
            log.warning("session_validation_failed", error=str(exc))
            return False
        except Exception as exc:  # defensive fallback for closed pages/adapters
            log.warning("session_validation_failed", error=str(exc))
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
                log.warning("Failed to delete stale lock %s: %s", lock_path, e)

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
                "browser_launch_failed_retrying",
                attempt=retry_state.attempt_number,
                next_wait_sec=sleep_val,
                error=str(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
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
        """Manage persistent Chromium browser context with session caching and asset optimization."""
        cfg.session_path.mkdir(parents=True, exist_ok=True)
        # Restore the execute bit on the profile dir: Chromium needs it to create
        # its ProcessSingleton lock, and a pre-existing dir with a missing x bit
        # would otherwise fail with "Permission denied" at launch. mkdir(exist_ok=True)
        # never repairs an already-broken directory, so chmod explicitly.
        # 0o700 is owner-only rwx — the most restrictive mode that still lets the
        # browser traverse the profile dir; nothing is granted to group/other.
        # Codacy's "insecure-file-permissions" finding here is a false positive.
        try:
            cfg.session_path.chmod(0o700)  # nosemgrep: insecure-file-permissions
        except OSError as e:
            log.debug("failed_setting_session_permissions", error=str(e))

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
            "user_data_dir": str(cfg.session_path),
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
                if cfg.mode != "login":
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
                    def on_request_failed(request: Any) -> None:
                        log.warning("browser_request_failed", url=_sanitize_url(request.url), error=request.failure)

                    def on_console(message: Any) -> None:
                        if message.type in {"error", "warning"}:
                            log.warning("browser_console_message", type=message.type, text=message.text)

                    def on_request(request: Any) -> None:
                        if request.method in {"POST", "PUT", "PATCH"} and "qwen.ai" in request.url:
                            log.info("browser_mutation_request", method=request.method, url=_sanitize_url(request.url))

                    def on_response(response: Any) -> None:
                        url = response.url.lower()
                        if response.status >= 400 and any(
                            token in url for token in ("chat", "completion", "generate", "conversation", "api")
                        ):
                            log.warning("browser_http_error", status=response.status, url=_sanitize_url(response.url))
                        elif response.request.method in {"POST", "PUT", "PATCH"} and "qwen.ai" in url:
                            log.info(
                                "browser_mutation_response", status=response.status, url=_sanitize_url(response.url)
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
                        log.warning("browser_context_cleanup_failed", error=str(e))
        except AuthRequiredError:
            raise
        except BrowserLaunchError:
            raise
        except Exception as e:
            if context_started:
                raise
            log.critical("browser_launch_failed", error=str(e))
            raise BrowserLaunchError(f"Failed to launch browser: {e}") from e

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of BrowserAdapter."""
        return "BrowserAdapter()"
