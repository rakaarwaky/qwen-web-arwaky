"""Session limit checker.

``SessionLimitChecker`` (``ISessionLimitCheckerProtocol``) answers one
question: does the Qwen chat page behind *session* still reply, or is it
rate-limited?

It returns ``ACTIVE`` when the probe page is healthy and shows no provider
limit banner, and ``LIMITED`` when the limit banner is detected **or** the
probe timed out (a missing reply is treated as a limit signal).

An expired session is **not** a limit, so the checker never reports
``AUTH_REQUIRED`` — login detection is the :class:`SessionLoginChecker`
concern.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from modules.shared.src.common.taxonomy_core_constant import RATE_LIMIT_PATTERNS
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.session.contract_session_protocol import ISessionLimitCheckerProtocol
from modules.shared.src.session.taxonomy_session_vo import (
    HealthReason,
    SessionHealthResult,
    SessionInfo,
    SessionStatus,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from modules.shared.src.browser.contract_browser_protocol import IBrowserLifecycleProtocol


# Compiled patterns for performance
_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in RATE_LIMIT_PATTERNS]


# Block 1: Class Definition & Constructor


class SessionLimitChecker(ISessionLimitCheckerProtocol):
    """Probes whether the Qwen chat page behind a session is rate-limited."""

    #: Bounded ceiling on the whole probe; a stalled launch is a limit signal too.
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
        """Probe *session* and return the limit verdict (ACTIVE or LIMITED).

        A healthy page that is not rate-limited yields ``ACTIVE``. A
        provider limit banner, a probe timeout, or a launch failure all
        yield ``LIMITED``. Login expiry is not a limit verdict and is
        never produced here.
        """
        session_id = session.session_id
        if self._browser_lifecycle is None:
            return _limited(session_id, session.reason, "Browser seam not configured")

        cfg = self.build_cfg(session)
        cancel = self._new_cancel()
        probe_done = threading.Event()
        probe_task = asyncio.get_running_loop().run_in_executor(
            None,
            self._probe_limit,
            cfg,
            session_id,
            session.reason,
            cancel,
            probe_done,
        )
        try:
            return await asyncio.wait_for(probe_task, timeout=self._timeout)
        except asyncio.TimeoutError:
            # Ask the probe thread to tear its own browser context down; the
            # executor thread cannot be cancelled, so the probe must do it.
            cancel.set()
            deadline = time.monotonic() + self.CANCEL_JOIN_TIMEOUT_SECONDS
            while not probe_done.is_set() and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            return _limited(
                session_id,
                session.reason,
                f"Limit probe timed out after {self._timeout}s",
                reason=HealthReason.TIMEOUT.value,
            )
        except Exception as exc:
            return _limited(
                session_id,
                session.reason,
                f"Limit probe failed: {exc}",
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

    @staticmethod
    def _extract_limit_evidence(page: Page) -> str | None:
        """Extract matching rate-limit evidence from page body text."""
        try:
            body = page.inner_text("body") or ""
            for pattern in _compiled_patterns:
                match = pattern.search(body)
                if match:
                    return match.group(0)
        except Exception:
            pass
        return None

    @staticmethod
    def _page_is_usable(
        page: Page,
        cancel: threading.Event | None = None,
    ) -> bool:
        """True when the chat composer (textarea) is present on the page."""
        try:
            selector = "textarea"
            deadline = 3
            for _ in range(deadline):
                if cancel is not None and cancel.is_set():
                    return False
                if page.query_selector(selector):
                    return True
                page.wait_for_timeout(500)
            return False
        except Exception:
            return False

    @staticmethod
    def _body_is_rate_limited(page: Page) -> bool:
        """True when the page body text matches a known rate-limit notice."""
        try:
            body = (page.inner_text("body") or "").lower()
        except Exception:
            return False
        if not body:
            return False
        return any(pattern.search(body) for pattern in _compiled_patterns)

    def _probe_limit(
        self,
        cfg: AppConfig,
        session_id: str,
        prior_reason: str | None,
        cancel: threading.Event,
        probe_done: threading.Event,
    ) -> SessionHealthResult:
        """Synchronous probe running on a worker thread.

        Enters the ephemeral browser context via the lifecycle view, then
        checks the two limit predicates:
        1. ``_body_is_rate_limited`` → ``LIMITED``.
        2. page usable (composer present) → ``ACTIVE``.

        An expired session that still shows the composer is still
        ``ACTIVE`` for the limit checker; expiry is the login checker's
        concern.
        """
        if self._browser_lifecycle is None:
            return _limited(session_id, prior_reason, "Browser seam not configured")
        try:
            with self._browser_lifecycle.health_probe_page(cfg) as page:
                if cancel.is_set():
                    return _limited(session_id, prior_reason, "Limit probe cancelled before completing")

                if self._body_is_rate_limited(page):
                    evidence = self._extract_limit_evidence(page)
                    return SessionHealthResult(
                        session_id=session_id,
                        status=SessionStatus.LIMITED,
                        reason=HealthReason.QUOTA.value,
                        evidence=evidence or "Provider daily limit reached",
                        recovery_action="Session is rate-limited. Switch accounts or reduce request throughput.",
                    )

                if not self._page_is_usable(page, cancel):
                    return _limited(
                        session_id,
                        prior_reason,
                        "Chat composer not reachable — page may have timed out or rate-limited",
                    )

                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.ACTIVE,
                    reason=None,
                    evidence=None,
                    recovery_action=None,
                )
        except Exception as exc:
            return _limited(session_id, prior_reason, f"Limit probe failed: {exc}")
        finally:
            probe_done.set()

    def __repr__(self) -> str:
        return f"SessionLimitChecker(browser_lifecycle={self._browser_lifecycle!r}, timeout_seconds={self._timeout})"


def _limited(
    session_id: str,
    prior_reason: str | None,
    evidence: str,
    *,
    reason: str | None = None,
) -> SessionHealthResult:
    """Build a LIMITED verdict with a recovery action."""
    return SessionHealthResult(
        session_id=session_id,
        status=SessionStatus.LIMITED,
        reason=reason or prior_reason or HealthReason.QUOTA.value,
        evidence=evidence,
        recovery_action="Wait for quota reset or switch accounts.",
    )


__all__ = ["SessionLimitChecker"]
