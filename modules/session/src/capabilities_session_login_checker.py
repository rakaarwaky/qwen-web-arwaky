"""Session login checker.

``SessionLoginChecker`` (``ISessionLoginCheckerProtocol``) answers one
question: does the Qwen chat page behind *session* still carry an
authenticated account?

It returns ``ACTIVE`` when the probe page shows the authenticated chat UI
and a live composer, and ``AUTH_REQUIRED`` when the page is a login/guest
view, shows an expiry banner, or the probe could not open an
authenticated page at all.

A rate-limited page that is still signed in is **not** a login failure, so
the checker never reports ``LIMITED`` — limit detection is the
:class:`SessionLimitChecker` concern.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from modules.shared.src.browser.utility_browser_session_check import (
    assert_on_chat_page,
    page_is_expired,
    session_is_alive,
)
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.session.contract_session_protocol import ISessionLoginCheckerProtocol
from modules.shared.src.session.taxonomy_session_vo import (
    HealthReason,
    SessionHealthResult,
    SessionInfo,
    SessionStatus,
)

if TYPE_CHECKING:
    from modules.shared.src.browser.contract_browser_protocol import IBrowserLifecycleProtocol


# Block 1: Class Definition & Constructor


class SessionLoginChecker(ISessionLoginCheckerProtocol):
    """Probes whether the Qwen chat page behind a session is authenticated."""

    #: Bounded ceiling on the whole probe; a stalled launch is a login failure too.
    DEFAULT_TIMEOUT_SECONDS = 60.0

    #: Grace given to a cancelled probe thread to tear down its own browser context.
    CANCEL_JOIN_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        browser_lifecycle: IBrowserLifecycleProtocol | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        session_cfg: AppConfig | None = None,
    ) -> None:
        self._browser_lifecycle = browser_lifecycle
        self._timeout = timeout_seconds
        self._session_cfg = session_cfg
        self._new_cancel: Callable[[], threading.Event] = threading.Event

    # Block 2: Protocol Method Implementation

    async def check_session(self, session: SessionInfo) -> SessionHealthResult:
        """Probe *session* and return the login verdict (ACTIVE or AUTH_REQUIRED).

        A successful authenticated probe yields ``ACTIVE``. Any failure —
        expired session, login form visible, composer missing, launch
        error, or probe timeout — yields ``AUTH_REQUIRED``. Rate-limit
        verdicts are the limit checker's job and are never produced here.
        """
        session_id = session.session_id
        if self._browser_lifecycle is None:
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.LAUNCH_FAILURE.value,
                evidence="Browser seam not configured",
                recovery_action="Configure the Playwright Chromium browser seam.",
            )

        cfg = self.build_cfg(session)
        cancel = self._new_cancel()
        probe_done = threading.Event()
        probe_task = asyncio.get_running_loop().run_in_executor(
            None,
            self._probe_login,
            cfg,
            session_id,
            cancel,
            probe_done,
        )
        try:
            return await asyncio.wait_for(probe_task, timeout=self._timeout)
        except asyncio.TimeoutError:
            cancel.set()
            deadline = time.monotonic() + self.CANCEL_JOIN_TIMEOUT_SECONDS
            while not probe_done.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.TIMEOUT.value,
                evidence=f"Login probe timed out after {self._timeout}s",
                recovery_action="Check network connection and responsiveness of chat.qwen.ai.",
            )
        except Exception as exc:
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.LAUNCH_FAILURE.value,
                evidence=str(exc),
                recovery_action="Verify Chromium installation and profile permissions.",
            )

    def build_cfg(self, session: SessionInfo) -> AppConfig:
        """Point the probe at *session*'s stored profile, reusing the base cfg's flags."""
        base = self._session_cfg
        if base is None:
            return AppConfig(
                input_path=session.path,
                output_path=session.path,
                session_path=session.path,
            )
        return AppConfig(
            input_path=base.input_path,
            output_path=base.output_path,
            session_path=session.path,
            log_path=base.log_path,
            mode=base.mode,
            interval=base.interval,
            timeout=base.timeout,
            headless=base.headless,
            verbose=base.verbose,
            prompt_file=base.prompt_file,
            prompt_path=base.prompt_path,
            file_path=base.file_path,
            chrome_profile=base.chrome_profile,
            storage_state_file=base.storage_state_file,
            disable_sandbox=base.disable_sandbox,
            request_timeout=base.request_timeout,
            poll_interval=base.poll_interval,
            streaming_timeout=base.streaming_timeout,
            inline_prompt=base.inline_prompt,
            inline_prompt_text=base.inline_prompt_text,
        )

    # Block 3: Dunder Methods, Factories, Helpers

    def _probe_login(
        self,
        cfg: AppConfig,
        session_id: str,
        cancel: threading.Event,
        probe_done: threading.Event,
    ) -> SessionHealthResult:
        """Synchronous probe running on a worker thread.

        Enters the ephemeral browser context via the lifecycle view, then
        runs the three login predicates in order:
        1. ``assert_on_chat_page`` raises on login/guest/expired views.
        2. ``page_is_expired`` catches in-page session-expiry banners.
        3. ``session_is_alive`` confirms the chat UI is responsive and
           the composer is present.

        All three pass → ``ACTIVE``. Any failure → ``AUTH_REQUIRED``.
        """
        if self._browser_lifecycle is None:
            return _auth_required(session_id, HealthReason.LAUNCH_FAILURE, "Browser seam not configured")
        try:
            with self._browser_lifecycle.health_probe_page(cfg) as page:
                if cancel.is_set():
                    return _auth_required(session_id, HealthReason.TIMEOUT, "Login probe cancelled before completing")
                if page_is_expired(page):
                    return _auth_required(
                        session_id,
                        HealthReason.EXPIRED,
                        "In-page session-expiry notice detected on the chat page",
                    )
                try:
                    assert_on_chat_page(page)
                except AuthRequiredError as exc:
                    return _auth_required(session_id, HealthReason.EXPIRED, str(exc))
                try:
                    if not session_is_alive(page):
                        return _auth_required(
                            session_id,
                            HealthReason.EXPIRED,
                            "Chat input / composer not usable or login prompt displayed",
                        )
                except Exception as exc:
                    return _auth_required(
                        session_id,
                        HealthReason.LAUNCH_FAILURE,
                        f"Login probe failed: {exc}",
                    )
                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.ACTIVE,
                    reason=None,
                    evidence=None,
                    recovery_action=None,
                )
        except AuthRequiredError as exc:
            return _auth_required(session_id, HealthReason.EXPIRED, str(exc))
        except Exception as exc:
            return _auth_required(
                session_id,
                HealthReason.LAUNCH_FAILURE,
                f"Login probe failed: {exc}",
            )
        finally:
            probe_done.set()

    def __repr__(self) -> str:
        return f"SessionLoginChecker(browser_lifecycle={self._browser_lifecycle!r}, timeout_seconds={self._timeout})"


def _auth_required(session_id: str, reason: HealthReason, evidence: str) -> SessionHealthResult:
    """Build an AUTH_REQUIRED verdict with a login-recovery action."""
    return SessionHealthResult(
        session_id=session_id,
        status=SessionStatus.AUTH_REQUIRED,
        reason=reason.value,
        evidence=evidence,
        recovery_action="Run `qwen-web-arwaky session login` to re-authenticate.",
    )


__all__ = ["SessionLoginChecker"]
