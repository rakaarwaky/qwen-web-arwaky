"""Browser lifecycle capability (Playwright adaptation).

Capabilities layer: implements IBrowserLifecycleProtocol. Owns the Playwright
process group: launch/teardown, ephemeral-context probes, and
master-profile renewal.

AES201: this capability never imports a sibling capability. Cross-capability
needs are reached through injected contracts:
- navigation (goto + auth assert) comes from the injected
  ``IBrowserNavigationProtocol``;
- diagnostics wiring (context-level route + per-page listeners) comes from
  the injected ``IBrowserDiagnosticsProtocol``.

The composition root wires the narrow views onto one shared facade so every
view drives one Chromium process group.
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
    IBrowserDiagnosticsProtocol,
    IBrowserLifecycleProtocol,
    IBrowserNavigationProtocol,
)
from modules.shared.src.browser.utility_browser_async_loop import isolate_thread_event_loop
from modules.shared.src.browser.utility_browser_model_target import bind_target_model, target_model
from modules.shared.src.common.taxonomy_core_constant import (
    CHAT_URL,
    LAUNCH_RETRY_WAIT_SEC,
    NAVIGATION_TIMEOUT_MS,
)
from modules.shared.src.common.taxonomy_core_error import (
    AuthRequiredError,
    BrowserLaunchError,
)
from modules.shared.src.common.taxonomy_core_vo import AppConfig, ModelLabel
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.session.utility_session_cloner import clean_stale_locks
from modules.shared.src.update.utility_update_browser_binary import find_chrome_binary, is_headless_shell_binary

log = get_logger("browser")


# Block 1: Class Definition & Constructor


class BrowserLifecycle(IBrowserLifecycleProtocol):
    """Launch/teardown, ephemeral-context probes, and master-profile renewal.

    The single owner of the Playwright process group. Diagnostics is an
    injected contract, so this capability implements exactly one protocol
    (``IBrowserLifecycleProtocol``).
    """

    def __init__(
        self,
        navigation: IBrowserNavigationProtocol | None,
        diagnostics: IBrowserDiagnosticsProtocol,
    ) -> None:
        """Initialize BrowserLifecycle.

        *navigation* owns goto + auth-assert (used by ``_open_chat_page``);
        *diagnostics* owns the context-level route + listeners. The
        composition root injects both views so the lifecycle view drives
        one Chromium process group. *navigation* is passed last so the
        container can break the lifecycle/navigation DI cycle by setting
        ``lifecycle.navigation`` after both views exist.
        """
        self._navigation = navigation
        self._diagnostics = diagnostics

    @property
    def navigation(self) -> IBrowserNavigationProtocol:
        """The injected navigation view (set after the container breaks
        the lifecycle/navigation DI cycle)."""
        assert self._navigation is not None, "navigation not wired"
        return self._navigation

    @navigation.setter
    def navigation(self, value: IBrowserNavigationProtocol) -> None:
        """Assign the navigation view (used by the container to break the DI cycle)."""
        self._navigation = value

    # Block 2: Public Contract

    @contextmanager
    def browser_session(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> Iterator[BrowserContext]:
        """Manage persistent Chromium browser context with session caching and asset optimization.

        For login mode, connects directly to the master session profile so credentials
        are saved permanently. For prompt jobs, runs in an isolated ephemeral copy of
        the session directory so multiple jobs can execute concurrently in parallel
        (1 browser process per job) without Chromium SingletonLock conflicts.

        ``session_path`` overrides the profile directory when provided
        (a plain path prepared by the session ``ProfilePreparer``); when
        omitted, the capability resolves it from *cfg.session_path*.
        ``executable_path`` is the Chromium binary to launch (injected by
        the update module); when omitted, the capability resolves it.
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

                self._diagnostics.wire_diagnostics(ctx)

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

    @contextmanager
    def health_probe_page(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
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

    def renew_session(
        self, cfg: AppConfig, session_path: Path | None = None, executable_path: str | None = None
    ) -> None:
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

    # Block 3: Dunder Methods, Factories & Helpers

    @contextmanager
    def _open_chat_page(
        self,
        cfg: AppConfig,
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
        ``ProfilePreparer``; when omitted the capability resolves it from
        *cfg.session_path*. The capability no longer clones the profile itself.
        """
        session_dir = session_path if session_path is not None else cfg.session_path
        kwargs = self._launch_kwargs(session_dir, cfg)
        with sync_playwright() as p:
            ctx = self._launch_context(p, kwargs)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                self.navigation.open_chat_page(page, strict=strict_auth)
                yield page
            finally:
                ctx.close()

    def _launch_kwargs(self, session_dir: Path, cfg: AppConfig) -> dict[str, Any]:
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

    def __repr__(self) -> str:
        """Return string representation of BrowserLifecycle."""
        return "BrowserLifecycle()"


__all__ = ["BrowserLifecycle"]
