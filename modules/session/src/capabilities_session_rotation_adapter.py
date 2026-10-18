"""Session rotation orchestrator — transparent session rotation for API calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from modules.shared.src.session.contract_session_protocol import (
    ISessionHealthCheckerProtocol,
    ISessionManagerProtocol,
    ISessionRotatorProtocol,
)
from modules.shared.src.session.taxonomy_session_vo import (
    RotatorRequest,
    RotatorResponse,
    SessionId,
    SessionInfo,
    SessionPool,
    SessionStatus,
)

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
    """Deprecated exception: callers branch on RotatorResponse.outcome == 'no_eligible_session'."""

    def __init__(self, pool: SessionPool | None = None) -> None:
        count = pool.total_count if pool else 0
        super().__init__(
            f"All {count} sessions are rate-limited. Please reduce request throughput or add authorized accounts."
        )


# Block 1: Class Definition & Constructor


class SessionRotationAdapter(ISessionRotatorProtocol):
    """Transparent session rotation with health checking."""

    def __init__(
        self,
        session_manager: ISessionManagerProtocol,
        health_checker: ISessionHealthCheckerProtocol | None = None,
    ) -> None:
        self._manager = session_manager
        self._checker: ISessionHealthCheckerProtocol | None = health_checker
        self._metrics = RotationMetrics()

    # Block 2: Protocol Method Implementation

    async def get_next_session(self) -> SessionInfo | None:
        """Get next healthy session with fallback."""
        resp = await self.rotate(RotatorRequest())
        return resp.session

    async def rotate(self, request: RotatorRequest) -> RotatorResponse:
        """Return the next healthy session, skipping ones already tried.

        ``request.exclude_ids`` lists sessions a caller has already attempted
        in this turn, so a rotation that hits a rate-limited session moves on
        rather than re-picking the one that just failed. When no eligible session
        remains, returns an explicit `no_eligible_session` outcome BEFORE
        submitting; never submits through a known-LIMITED profile.
        """
        self._metrics.total_attempts += 1
        pool = self._manager.load_pool()
        if not pool.sessions:
            self._metrics.sessions_exhausted += 1
            return RotatorResponse(
                session=None,
                outcome="no_eligible_session",
                reason="empty_pool",
                recovery_action=(
                    "No sessions configured. Run 'qwen-web-arwaky session login --name <name>' "
                    "to add an authorized session."
                ),
            )

        excluded = set(request.exclude_ids)
        checker = self._ensure_checker()

        for candidate in pool.sessions:
            if candidate.session_id in excluded:
                continue
            verdict = await checker.diagnose_session(candidate)
            if verdict.is_healthy:
                self._manager.mark_healthy(candidate.session_id)
                self._metrics.successful_rotations += 1
                return RotatorResponse(session=candidate, outcome="success")
            elif verdict.status == SessionStatus.LIMITED:
                self._manager.mark_limited(candidate.session_id, reason=verdict.reason)
            else:
                self._manager.mark_auth_required(candidate.session_id, reason=verdict.reason)

        self._metrics.sessions_exhausted += 1
        all_excluded = bool(excluded) and all(s.session_id in excluded for s in pool.sessions)
        reason = "all_sessions_excluded" if all_excluded else "all_sessions_limited"
        return RotatorResponse(
            session=None,
            outcome="no_eligible_session",
            reason=reason,
            recovery_action=(
                "All sessions in the pool are rate-limited or excluded. "
                "Reduce request throughput or add authorized accounts."
            ),
        )

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
    ) -> tuple[str, SessionInfo | None]:
        """Execute request with automatic session rotation.

        Returns (response, used_session). When no eligible session exists,
        returns an explicit error outcome without submitting.
        """
        self._metrics.total_attempts += 1

        rot_resp = await self.rotate(RotatorRequest())
        if rot_resp.session is None or rot_resp.outcome == "no_eligible_session":
            return (
                f"ERROR: no_eligible_session [{rot_resp.reason}]: {rot_resp.recovery_action}",
                None,
            )

        session = rot_resp.session
        response = await self._execute_request(prompt, attachment, session)

        pool = self._manager.load_pool()
        updated = session.with_usage(success=True)
        pool.sessions = [updated if s.session_id == session.session_id else s for s in pool.sessions]
        self._manager.save_pool(pool)

        return response, session

    @property
    def metrics(self) -> RotationMetrics:
        """Get rotation metrics."""
        return self._metrics

    # Block 3: Dunder Methods, Factories & Helpers

    def _ensure_checker(self) -> ISessionHealthCheckerProtocol:
        """Return the health checker, raising if not configured."""
        if self._checker is None:
            raise RuntimeError("Health checker not configured — pass one to SessionRotationAdapter()")
        return self._checker

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


__all__ = [
    "SessionRotationAdapter",
    "AllSessionsLimitedError",
    "RotationMetrics",
]
