"""Session health checker — real browser ping to detect rate limits and expired sessions."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from modules.shared.src.common.taxonomy_core_constant import RATE_LIMIT_PATTERNS
from modules.shared.src.common.taxonomy_core_error import AuthRequiredError
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.session.contract_session_protocol import ISessionHealthCheckerProtocol, ISessionManagerProtocol
from modules.shared.src.session.taxonomy_session_vo import (
    HealthReason,
    SessionHealthResult,
    SessionId,
    SessionInfo,
    SessionPool,
    SessionStatus,
)

if TYPE_CHECKING:
    from modules.shared.src.browser.contract_browser_protocol import IBrowserProtocol


# Compiled patterns for performance
_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in RATE_LIMIT_PATTERNS]

# A read-only liveness probe: it proves the session's saved Chromium profile still
# unlocks an authenticated chat page (and that the chat UI is not rate-limited),
# without submitting a prompt, so the check itself never burns the account's
# request budget.


# Block 1: Class Definition & Constructor
class SessionHealthChecker(ISessionHealthCheckerProtocol):
    """Checks session health with a real browser ping against the session profile."""

    #: Bounded ceiling on the whole probe; a stalled launch is a limit signal too.
    DEFAULT_TIMEOUT_SECONDS = 60.0

    def __init__(
        self,
        browser: IBrowserProtocol | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        session_cfg: AppConfig | None = None,
    ) -> None:
        self._browser = browser
        self._timeout = timeout_seconds
        self._session_cfg = session_cfg

    # Block 2: Protocol Method Implementation
    async def check_session(self, session: SessionInfo) -> bool:
        """Return True when *session* is healthy (auth valid and not rate-limited).

        Delegates to :meth:`diagnose_session` and checks for ACTIVE status.
        """
        verdict = await self.diagnose_session(session)
        return verdict.is_healthy

    async def diagnose_session(self, session: SessionInfo) -> SessionHealthResult:
        """Probe *session* and return the reasoned SessionHealthResult.

        Follows locked rules:
        - ACTIVE only from successful authenticated probe.
        - LIMITED only from observed provider-limit evidence (limit banner/signal).
        - AUTH_REQUIRED for any other failed probe: expired login, browser launch
          failure, network error, timeout.
        - Probe failure MUST NOT overwrite a confirmed LIMITED verdict with invented
          quota evidence (transient failure on LIMITED session leaves it LIMITED).
        """
        session_id = session.session_id
        if self._browser is None:
            if session.status == SessionStatus.LIMITED:
                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.LIMITED,
                    reason=session.reason or HealthReason.QUOTA.value,
                    evidence="Retained prior quota limit during browser unconfigured state",
                    recovery_action="Wait for quota reset or switch accounts.",
                )
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.LAUNCH_FAILURE.value,
                evidence="Browser seam not configured",
                recovery_action="Configure Playwright Chromium browser seam.",
            )

        cfg = self._build_cfg(session)
        loop = asyncio.get_running_loop()
        probe_task = loop.run_in_executor(
            None,
            self._probe_verdict,
            cfg,
            session.session_id,
            session.status,
            session.reason,
        )
        try:
            return await asyncio.wait_for(probe_task, timeout=self._timeout)
        except asyncio.TimeoutError:
            if session.status == SessionStatus.LIMITED:
                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.LIMITED,
                    reason=session.reason or HealthReason.QUOTA.value,
                    evidence="Retained prior quota limit during transient probe timeout",
                    recovery_action="Wait for quota reset or switch accounts.",
                )
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.TIMEOUT.value,
                evidence=f"Health probe timed out after {self._timeout}s",
                recovery_action="Check network connection and responsiveness of chat.qwen.ai.",
            )
        except Exception as exc:
            if session.status == SessionStatus.LIMITED:
                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.LIMITED,
                    reason=session.reason or HealthReason.QUOTA.value,
                    evidence=f"Retained prior quota limit during transient probe failure: {exc}",
                    recovery_action="Wait for quota reset or switch accounts.",
                )
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.LAUNCH_FAILURE.value,
                evidence=str(exc),
                recovery_action="Verify Chromium installation and profile permissions.",
            )

    async def check_all_sessions(self, pool: SessionPool) -> SessionPool:
        """Health-check every session and return the updated pool."""
        tasks = [self.diagnose_session(s) for s in pool.sessions]
        results = await asyncio.gather(*tasks)

        updated = []
        for session, verdict in zip(pool.sessions, results, strict=True):
            updated.append(session.with_status(verdict.status, reason=verdict.reason))

        return SessionPool(sessions=updated, current_index=pool.current_index)

    def check_pool_sync(
        self,
        pool: SessionPool,
        session_manager: ISessionManagerProtocol,
    ) -> list[tuple[SessionInfo, SessionHealthResult]]:
        """Synchronous convenience wrapper: check all sessions and update manager state."""

        async def _run() -> list[tuple[SessionInfo, SessionHealthResult]]:
            results: list[tuple[SessionInfo, SessionHealthResult]] = []
            for s in pool.sessions:
                verdict = await self.diagnose_session(s)
                results.append((s, verdict))
                if verdict.status == SessionStatus.ACTIVE:
                    session_manager.mark_healthy(s.session_id)
                elif verdict.status == SessionStatus.LIMITED:
                    session_manager.mark_limited(s.session_id, reason=verdict.reason)
                else:
                    session_manager.mark_auth_required(s.session_id, reason=verdict.reason)
            return results

        return asyncio.run(_run())

    def summarize_pool_results(self, results: list[tuple[SessionInfo, SessionHealthResult]]) -> tuple[int, int]:
        """Return ``(healthy_count, total)`` for a pool-check result list."""
        healthy_count = sum(1 for _, verdict in results if verdict.is_healthy)
        return healthy_count, len(results)

    # Block 3: Dunder Methods, Factories, Helpers
    def _build_cfg(self, session: SessionInfo) -> AppConfig:
        """Point the probe at *session*'s stored profile, reusing the base cfg's flags."""
        base = self._session_cfg
        if base is None:
            # No base config (e.g. a standalone unit test): a minimal cfg whose
            # profile is *session*'s path. The prompt/output inputs are unused
            # by the probe.
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

    def _probe_verdict(
        self,
        cfg: AppConfig,
        session_id: SessionId,
        prior_status: SessionStatus,
        prior_reason: str | None,
    ) -> SessionHealthResult:
        """Synchronous probe returning a reasoned SessionHealthResult.

        Runs on a worker thread to keep the asyncio event loop unblocked.
        """
        if self._browser is None:
            if prior_status == SessionStatus.LIMITED:
                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.LIMITED,
                    reason=prior_reason or HealthReason.QUOTA.value,
                    evidence="Retained prior quota limit",
                    recovery_action="Wait for quota reset or switch accounts.",
                )
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.LAUNCH_FAILURE.value,
                evidence="Browser seam not configured",
                recovery_action="Install Chromium via 'python -m playwright install chromium'.",
            )

        try:
            with self._browser.health_probe_page(cfg) as page:
                if self._body_is_rate_limited(page):
                    evidence = self._extract_limit_evidence(page)
                    return SessionHealthResult(
                        session_id=session_id,
                        status=SessionStatus.LIMITED,
                        reason=HealthReason.QUOTA.value,
                        evidence=evidence or "Provider daily limit reached",
                        recovery_action="Session is rate-limited. Switch accounts or reduce request throughput.",
                    )

                if not self._page_is_usable(page):
                    return SessionHealthResult(
                        session_id=session_id,
                        status=SessionStatus.AUTH_REQUIRED,
                        reason=HealthReason.EXPIRED.value,
                        evidence="Chat input / composer not usable or login prompt displayed",
                        recovery_action="Run 'qwen-web-arwaky session login' to authenticate.",
                    )

                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.ACTIVE,
                    reason=None,
                    evidence=None,
                    recovery_action=None,
                )
        except AuthRequiredError as exc:
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=HealthReason.EXPIRED.value,
                evidence=str(exc),
                recovery_action="Session expired. Run 'qwen-web-arwaky session login' to re-authenticate.",
            )
        except Exception as exc:
            err_msg = str(exc)
            err_lower = err_msg.lower()
            if prior_status == SessionStatus.LIMITED:
                return SessionHealthResult(
                    session_id=session_id,
                    status=SessionStatus.LIMITED,
                    reason=prior_reason or HealthReason.QUOTA.value,
                    evidence=f"Retained prior quota limit during probe error: {err_msg}",
                    recovery_action="Wait for quota reset or switch accounts.",
                )
            if "timeout" in err_lower:
                reason = HealthReason.TIMEOUT.value
                action = "Check network responsiveness of chat.qwen.ai."
            elif any(net_kw in err_lower for net_kw in ("net::", "connection", "dns", "network", "refused", "resolve")):
                reason = HealthReason.NETWORK.value
                action = "Check network connection to chat.qwen.ai."
            else:
                reason = HealthReason.LAUNCH_FAILURE.value
                action = "Verify browser launch and profile directory permissions."
            return SessionHealthResult(
                session_id=session_id,
                status=SessionStatus.AUTH_REQUIRED,
                reason=reason,
                evidence=err_msg,
                recovery_action=action,
            )

    @staticmethod
    def _extract_limit_evidence(page: Any) -> str | None:
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
    def _page_is_usable(page: Any) -> bool:
        """True when the chat composer (textarea) is present on the page."""
        try:
            selector = "textarea"
            deadline = 3
            for _ in range(deadline):
                if page.query_selector(selector):
                    return True
                page.wait_for_timeout(500)
            return False
        except Exception:
            return False

    @staticmethod
    def _body_is_rate_limited(page: Any) -> bool:
        """True when the page body text matches a known rate-limit notice."""
        try:
            body = (page.inner_text("body") or "").lower()
        except Exception:
            return False
        if not body:
            return False
        return any(pattern.search(body) for pattern in _compiled_patterns)

    def __repr__(self) -> str:
        """Return string representation of the health checker."""
        return f"SessionHealthChecker(browser={self._browser!r}, timeout_seconds={self._timeout})"


__all__ = ["SessionHealthChecker"]
