"""Session health checker — real browser ping to detect rate limits and expired sessions."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from modules.shared.src.common.taxonomy_core_constant import RATE_LIMIT_PATTERNS
from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.session.contract_session_protocol import ISessionHealthCheckerProtocol, ISessionManagerProtocol
from modules.shared.src.session.taxonomy_session_vo import SessionInfo, SessionPool, SessionStatus

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

        Launches a fresh Chromium context on *session*'s stored profile via the
        injected browser seam and runs the read-only liveness probe in a worker
        thread so the asyncio event loop is never blocked by Playwright's
        synchronous API. Any exception — auth-required (expired token / login
        redirect), rate-limit banner, or a launch stall past ``timeout_seconds``
        — marks the session unhealthy and is swallowed to ``False``.
        """
        if self._browser is None:
            return False
        cfg = self._build_cfg(session)
        loop = asyncio.get_running_loop()
        probe = loop.run_in_executor(None, self._probe, cfg)
        try:
            return await asyncio.wait_for(probe, timeout=self._timeout)
        except (asyncio.TimeoutError, Exception):
            return False

    async def check_all_sessions(self, pool: SessionPool) -> SessionPool:
        """Health-check every session and return the updated pool."""
        tasks = [self.check_session(s) for s in pool.sessions]
        results = await asyncio.gather(*tasks)

        updated = []
        for session, healthy in zip(pool.sessions, results, strict=True):
            new_status = SessionStatus.ACTIVE if healthy else SessionStatus.LIMITED
            updated.append(session.with_status(new_status))

        return SessionPool(sessions=updated, current_index=pool.current_index)

    def check_pool_sync(
        self,
        pool: SessionPool,
        session_manager: ISessionManagerProtocol,
    ) -> list[tuple[SessionInfo, bool]]:
        """Synchronous convenience wrapper: check all sessions and update manager state."""
        import asyncio as _asyncio

        async def _run() -> list[tuple[SessionInfo, bool]]:
            results: list[tuple[SessionInfo, bool]] = []
            for s in pool.sessions:
                healthy = await self.check_session(s)
                results.append((s, healthy))
                if healthy:
                    session_manager.mark_healthy(s.session_id)
                else:
                    session_manager.mark_limited(s.session_id)
            return results

        return _asyncio.run(_run())

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

    def _probe(self, cfg: AppConfig) -> bool:
        """Synchronous liveness probe: open the page, assert auth, scan for limits.

        Runs on a worker thread (Playwright's sync API is thread-blocking).
        Returns True only when the chat page is authenticated AND its body does
        not carry a rate-limit notice.
        """
        if self._browser is None:
            return False
        try:
            with self._browser.health_probe_page(cfg) as page:
                if not self._page_is_usable(page):
                    return False
                return not self._body_is_rate_limited(page)
        except Exception:
            return False

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
