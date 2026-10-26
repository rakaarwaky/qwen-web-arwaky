"""Session rotation orchestrator — transparent session rotation for API calls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptText
from modules.shared.src.session.contract_session_protocol import (
    ISessionLimitCheckerProtocol,
    ISessionManagerProtocol,
    ISessionRotatorProtocol,
)
from modules.shared.src.session.taxonomy_session_vo import (
    RotatorRequest,
    RotatorResponse,
    SessionId,
    SessionInfo,
    SessionStatus,
)


@dataclass
class RotationMetrics:
    """Metrics for session rotation."""

    total_attempts: int = 0
    successful_rotations: int = 0
    sessions_exhausted: int = 0
    average_rotation_time_ms: float = 0.0


#: Caller-facing recovery prose for the ``no_eligible_session`` reasons
#: that share one action (``empty_pool`` carries its own).
_NO_ELIGIBLE_RECOVERY: dict[str, str] = {
    reason: (
        "All sessions in the pool are rate-limited or excluded. Reduce request throughput or add authorized accounts."
    )
    for reason in ("all_sessions_limited", "all_sessions_excluded")
}


# Block 1: Class Definition & Constructor


class SessionRotationAdapter(ISessionRotatorProtocol):
    """Transparent session rotation with health checking."""

    def __init__(
        self,
        session_manager: ISessionManagerProtocol,
        limit_checker: ISessionLimitCheckerProtocol | None = None,
        prompt: IPromptAggregate | None = None,
    ) -> None:
        self._manager = session_manager
        self._checker: ISessionLimitCheckerProtocol | None = limit_checker
        self._prompt: IPromptAggregate | None = prompt
        self._metrics = RotationMetrics()

    # Block 2: Protocol Method Implementation

    async def get_next_session(self) -> SessionInfo | None:
        """Get next healthy session with fallback.

        Delegates to :meth:`rotate` so the two never drift: a single
        ordered pass from ``pool.current_index`` probes each candidate
        exactly once, so an all-limited pool of N sessions costs N probes.
        """
        resp = await self.rotate(RotatorRequest())
        return resp.session

    async def rotate(self, request: RotatorRequest) -> RotatorResponse:
        """Return the next healthy session, skipping ones already tried.

        ``request.exclude_ids`` lists sessions a caller has already attempted
        in this turn, so a rotation that hits a rate-limited session moves on
        rather than re-picking the one that just failed. Iteration starts at
        ``pool.current_index`` and wraps, so the same pool state always
        resolves the same candidate (FR-SESSION-002 determinism); each
        candidate is probed exactly once. When no eligible session remains,
        returns an explicit ``no_eligible_session`` outcome BEFORE
        submitting (``throttled`` reads True on that outcome); never
        submits through a known-LIMITED profile.
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
        ordered = pool.sessions[pool.current_index :] + pool.sessions[: pool.current_index]

        for candidate in ordered:
            if candidate.session_id in excluded:
                continue
            verdict = await checker.check_session(candidate)
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
            recovery_action=_NO_ELIGIBLE_RECOVERY[reason],
        )

    async def mark_limited(self, session_id: SessionId) -> None:
        """Mark session as rate-limited."""
        self._manager.mark_limited(session_id)

    async def mark_healthy(self, session_id: SessionId) -> None:
        """Mark session as healthy."""
        self._manager.mark_healthy(session_id)

    def rotate_sync(self, request: RotatorRequest) -> RotatorResponse:
        """Synchronous wrapper that runs rotation on a fresh event loop.

        Mirrors ``check_pool_sync``: the capability owns the event-loop
        handling so the sync ``execute`` seam never calls ``asyncio.run``
        inline (which would crash inside an already-running loop).
        """
        return asyncio.run(self.rotate(request))

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
        response = self._execute_request(prompt, attachment, session)
        self._manager.mark_used(session.session_id, success=True)

        return response, session

    @property
    def metrics(self) -> RotationMetrics:
        """Get rotation metrics."""
        return self._metrics

    # Block 3: Dunder Methods, Factories & Helpers

    def _ensure_checker(self) -> ISessionLimitCheckerProtocol:
        """Return the limit checker, raising if not configured."""
        if self._checker is None:
            raise RuntimeError("Limit checker not configured — pass one to SessionRotationAdapter()")
        return self._checker

    def _execute_request(
        self,
        prompt: str,
        _attachment: object | None,
        session: SessionInfo,
    ) -> str:
        """Execute actual request via the injected prompt aggregate.

        Delegates to ``IPromptAggregate.execute`` with ``process_direct_prompt``
        so rotation produces a real response through the direct-prompt pipeline
        instead of a simulated one.
        """
        if self._prompt is None:
            raise RuntimeError(
                "SessionRotationAdapter has no IPromptAggregate wired — "
                "pass prompt=PromptOrchestrator(...) when constructing"
            )
        response = self._prompt.execute(
            PromptRequest(
                verb="process_direct_prompt",
                prompt=PromptText(prompt),
                session_resolver=lambda: session.path,
            )
        )
        return str(response.response_text or "")


__all__ = [
    "SessionRotationAdapter",
    "RotationMetrics",
]
