"""Session health checker — ping test to detect rate limits."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from modules.shared.src.contract_session_aggregate import ISessionHealthCheckerProtocol, ISessionManagerProtocol
from modules.shared.src.taxonomy_session_vo import SessionInfo, SessionPool, SessionStatus

if TYPE_CHECKING:
    pass


# Rate limit detection patterns
RATE_LIMIT_PATTERNS = [
    r"upper\s+limit",
    r"rate\s+limit",
    r"daily\s+limit",
    r"quota\s+exceeded",
    r"try\s+again\s+tomorrow",
    r"too\s+many\s+requests",
    r"429",
    r"limit\s+reached",
    r"usage\s+limit",
]

# Compiled patterns for performance
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in RATE_LIMIT_PATTERNS]


class SessionHealthChecker(ISessionHealthCheckerProtocol):
    """Checks session health via ping test."""

    PING_MESSAGE = "Reply with just: pong"
    EXPECTED_KEYWORD = "pong"

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self._timeout = timeout_seconds

    async def check_session(self, session: SessionInfo) -> bool:
        """Check if session is healthy.

        Returns True if session can accept requests, False if rate-limited.
        """
        try:
            response = await self._send_ping(session)
            return self._is_healthy(response)
        except Exception:
            return False

    async def check_all_sessions(self, pool: SessionPool) -> SessionPool:
        """Health check all sessions and return updated pool."""
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

    async def _send_ping(self, _session: SessionInfo) -> str:
        """Send ping message and get response.

        In real implementation, this would use Playwright to:
        1. Open browser with session profile
        2. Navigate to chat.qwen.ai
        3. Type ping message
        4. Wait for response
        5. Return response text
        """
        # For now, simulate async operation
        await asyncio.sleep(0.1)  # Simulate network delay
        return "pong"

    def _is_healthy(self, response: str) -> bool:
        """Check if response indicates rate limit."""
        if not response:
            return False

        response_lower = response.lower()

        # Check for rate limit patterns
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(response_lower):
                return False

        # Check for expected response
        if self.EXPECTED_KEYWORD in response_lower:
            return True

        return True  # Assume healthy if no limit detected


__all__ = ["SessionHealthChecker"]
