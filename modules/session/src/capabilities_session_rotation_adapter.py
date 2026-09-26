"""Session rotation orchestrator — transparent session rotation for API calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from modules.shared.src.contract_session_aggregate import (
    ISessionHealthCheckerProtocol,
    ISessionManagerProtocol,
    ISessionRotatorAggregate,
)
from modules.shared.src.taxonomy_session_vo import SessionId, SessionInfo, SessionPool

if TYPE_CHECKING:
    pass


@dataclass
class RotationMetrics:
    """Metrics for session rotation."""

    total_attempts: int = 0
    successful_rotations: int = 0
    sessions_exhausted: int = 0
    average_rotation_time_ms: float = 0.0


class AllSessionsLimitedError(Exception):
    """Raised when all sessions are rate-limited."""

    def __init__(self, pool: SessionPool) -> None:
        self.pool = pool
        super().__init__(
            f"All {pool.total_count} sessions are rate-limited. Please wait until tomorrow or add more sessions."
        )


class SessionRotationAdapter(ISessionRotatorAggregate):
    """Transparent session rotation with health checking."""

    def __init__(
        self,
        session_manager: ISessionManagerProtocol,
        health_checker: ISessionHealthCheckerProtocol | None = None,
    ) -> None:
        self._manager = session_manager
        self._checker: ISessionHealthCheckerProtocol | None = health_checker
        self._metrics = RotationMetrics()

    def _ensure_checker(self) -> ISessionHealthCheckerProtocol:
        """Return the health checker, raising if not configured."""
        if self._checker is None:
            raise RuntimeError("Health checker not configured — pass one to SessionRotationAdapter()")
        return self._checker

    async def get_next_session(self) -> SessionInfo | None:
        """Get next healthy session with fallback."""
        pool = self._manager.load_pool()

        # Try round-robin
        session = pool.get_next_session()
        if session:
            # Verify health
            checker = self._ensure_checker()
            is_healthy = await checker.check_session(session)
            if is_healthy:
                self._manager.mark_healthy(session.session_id)
                self._metrics.successful_rotations += 1
                return session
            else:
                self._manager.mark_limited(session.session_id)

        # Try all sessions
        checker = self._ensure_checker()
        for s in pool.sessions:
            is_healthy = await checker.check_session(s)
            if is_healthy:
                self._manager.mark_healthy(s.session_id)
                self._metrics.successful_rotations += 1
                return s
            else:
                self._manager.mark_limited(s.session_id)

        # All exhausted
        self._metrics.sessions_exhausted += 1
        return None

    async def mark_limited(self, session_id: SessionId) -> None:
        """Mark session as rate-limited."""
        self._manager.mark_limited(session_id)

    async def mark_healthy(self, session_id: SessionId) -> None:
        """Mark session as healthy."""
        self._manager.mark_healthy(session_id)

    async def execute_with_rotation(
        self,
        prompt: str,
        attachment: object | None = None,
    ) -> tuple[str, SessionInfo]:
        """Execute request with automatic session rotation.

        Returns (response, used_session).
        """
        self._metrics.total_attempts += 1

        session = await self.get_next_session()
        if session is None:
            pool = self._manager.load_pool()
            raise AllSessionsLimitedError(pool)

        # Execute with session (real implementation would use browser adapter)
        response = await self._execute_request(prompt, attachment, session)

        # Track usage
        pool = self._manager.load_pool()
        updated = session.with_usage(success=True)
        pool.sessions = [updated if s.session_id == session.session_id else s for s in pool.sessions]
        self._manager.save_pool(pool)

        return response, session

    async def _execute_request(
        self,
        prompt: str,
        _attachment: object | None,
        session: SessionInfo,
    ) -> str:
        """Execute actual request with session.

        In real implementation, this would:
        1. Launch browser with session profile
        2. Navigate to chat.qwen.ai
        3. Inject prompt
        4. Wait for response
        5. Return response text
        """
        # Simulated response for now
        return f"Response using session {session.session_id}: {prompt}"

    @property
    def metrics(self) -> RotationMetrics:
        """Get rotation metrics."""
        return self._metrics


__all__ = [
    "SessionRotationAdapter",
    "AllSessionsLimitedError",
    "RotationMetrics",
]
