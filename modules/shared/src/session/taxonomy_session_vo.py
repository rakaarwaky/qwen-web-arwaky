"""Session value objects — multi-account rate limit rotation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, NewType, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable


class SessionStatus(str, Enum):
    """Health status of a Qwen session."""

    ACTIVE = "active"  # Healthy, can send requests
    LIMITED = "limited"  # Hit rate limit
    AUTH_REQUIRED = "auth_required"  # Authentication required or probe failure
    # Read-only alias for legacy pool files; ``SessionStatus._missing_`` maps
    # a persisted ``"unknown"`` to AUTH_REQUIRED on load, and the next
    # ``save_pool`` rewrites the pool JSON in place as ``"auth_required"``.
    UNKNOWN = "auth_required"

    @classmethod
    def _missing_(cls, value: object) -> SessionStatus | None:
        if isinstance(value, str) and value.lower() == "unknown":
            return cls.AUTH_REQUIRED
        return None


class HealthReason(str, Enum):
    """Sub-cause reason for a session health probe verdict."""

    QUOTA = "QUOTA"
    EXPIRED = "EXPIRED"
    LAUNCH_FAILURE = "LAUNCH_FAILURE"
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"


SessionId: TypeAlias = str
SessionName: TypeAlias = str
#: Sub-cause reason for a health verdict, e.g. ``"QUOTA"`` or ``"EXPIRED"``.
#: Values are the :class:`HealthReason` constants; stored as plain strings.
SessionReason: TypeAlias = str


@dataclass(frozen=True)
class SessionHealthResult:
    """Detailed reasoned verdict for a session health probe."""

    session_id: SessionId
    status: SessionStatus
    reason: str | None = None
    evidence: str | None = None
    recovery_action: str | None = None

    @property
    def is_healthy(self) -> bool:
        """True if session is ACTIVE and ready to serve requests."""
        return self.status == SessionStatus.ACTIVE


@dataclass(frozen=True)
class SessionInfo:
    """Immutable metadata about a single Qwen login session."""

    session_id: SessionId
    name: SessionName
    path: Path
    status: SessionStatus = SessionStatus.AUTH_REQUIRED
    last_used: datetime | None = field(default=None)
    total_requests: int = field(default=0)
    failed_requests: int = field(default=0)
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    reason: str | None = field(default=None)

    @property
    def is_healthy(self) -> bool:
        """True if session can accept requests."""
        return self.status == SessionStatus.ACTIVE

    @property
    def is_limited(self) -> bool:
        """True if session has hit rate limit."""
        return self.status == SessionStatus.LIMITED

    @property
    def is_auth_required(self) -> bool:
        """True if session requires authentication or login."""
        return self.status == SessionStatus.AUTH_REQUIRED

    @property
    def failure_rate(self) -> float:
        """Ratio of failed requests (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    def with_status(self, status: SessionStatus, reason: SessionReason | None = None) -> SessionInfo:
        """Return a copy with updated status and optional reason."""
        return replace(self, status=status, reason=reason)

    def with_name(self, name: SessionName) -> SessionInfo:
        """Return a copy with an updated account name (delegates to ``dataclasses.replace``)."""
        return replace(self, name=name)

    def with_usage(self, success: bool) -> SessionInfo:
        """Return a copy with updated usage counters (delegates to ``dataclasses.replace``)."""
        return replace(
            self,
            last_used=datetime.now().astimezone(),
            total_requests=self.total_requests + 1,
            failed_requests=self.failed_requests + (0 if success else 1),
        )


@dataclass
class SessionPool:
    """Mutable collection of sessions with rotation logic."""

    sessions: list[SessionInfo] = field(default_factory=list)
    current_index: int = 0

    @classmethod
    def empty(cls) -> SessionPool:
        """Create an empty session pool."""
        return cls(sessions=[], current_index=0)

    @property
    def healthy_count(self) -> int:
        """Number of sessions that are not limited."""
        return sum(1 for s in self.sessions if s.is_healthy)

    @property
    def limited_count(self) -> int:
        """Number of sessions currently rate-limited."""
        return sum(1 for s in self.sessions if s.is_limited)

    @property
    def total_count(self) -> int:
        """Total number of sessions."""
        return len(self.sessions)

    def get_next_session(self) -> SessionInfo | None:
        """Get next healthy session using round-robin with fallback."""
        if not self.sessions:
            return None

        # Try from current position
        for offset in range(len(self.sessions)):
            idx = (self.current_index + offset) % len(self.sessions)
            session = self.sessions[idx]
            if session.is_healthy:
                self.current_index = (idx + 1) % len(self.sessions)
                return session

        # All sessions limited
        return None

    def mark_limited(self, session_id: str, reason: SessionReason | None = "QUOTA") -> None:
        """Mark a session as rate-limited; ``None`` is persisted as ``"QUOTA"``."""
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                self.sessions[i] = s.with_status(SessionStatus.LIMITED, reason=reason)
                return

    def mark_healthy(self, session_id: str) -> None:
        """Mark a session as healthy after successful request or probe."""
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                self.sessions[i] = s.with_status(SessionStatus.ACTIVE, reason=None)
                return

    def mark_auth_required(self, session_id: str, reason: SessionReason | None = None) -> None:
        """Mark a session as requiring re-authentication or setup."""
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                self.sessions[i] = s.with_status(SessionStatus.AUTH_REQUIRED, reason=reason)
                return

    def add_session(self, info: SessionInfo) -> None:
        """Add a new session to the pool."""
        self.sessions.append(info)

    def remove_session(self, session_id: str) -> bool:
        """Remove a session by ID. Returns True if found."""
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                self.sessions.pop(i)
                return True
        return False

    def get_session(self, session_id: str) -> SessionInfo | None:
        """Get a session by ID."""
        for s in self.sessions:
            if s.session_id == session_id:
                return s
        return None

    def get_ordered_sessions(self) -> list[SessionInfo]:
        """Get all sessions ordered by health (healthy first)."""
        return sorted(
            self.sessions,
            key=lambda s: (s.is_limited, s.last_used),
            reverse=True,
        )


#: The session records a listing verb returned, in pool order. Declared as
#: a NewType so the contract signature carries one named domain type
#: rather than a bare list primitive (AES402).
SessionList = NewType("SessionList", list[SessionInfo])


@dataclass(frozen=True)
class RotatorRequest:
    """One rotation verb plus the selection policy to apply.

    ``exclude_ids`` names sessions a caller already tried in this turn,
    so a rotation can step past them instead of re-picking the session
    that just failed.
    """

    verb: str = "rotate"
    exclude_ids: tuple[SessionId, ...] = ()


@dataclass(frozen=True)
class RotatorResponse:
    """What a rotation verb produced.

    ``session`` carries the selected healthy session. When no healthy session
    remains, ``session`` is None and ``outcome`` is "no_eligible_session" with
    an explicit reason and recovery action; ``error`` is reserved for a
    rotation that could not be attempted at all.
    """

    session: SessionInfo | None = None
    error: str | None = None
    outcome: str = "success"
    reason: str | None = None
    recovery_action: str | None = None


@dataclass(frozen=True)
class SessionRequest:
    """One session verb plus everything the agent needs to run it.

    ``validate`` reads ``session_path`` to locate the profile;
    ``delete`` reads it and ``force`` to bypass the no-backup guard that
    protects the master profile from accidental deletion; ``login`` reads
    ``session_path`` (or ``name`` under ``SESSIONS_DIR``) and
    ``wait_for_confirmation``; ``list_sessions`` returns the whole pool in
    pool order; ``remove_session`` reads ``session_path`` (or ``name``) and
    ``force``. Fields the chosen verb does not read stay
    at their defaults, so no verb passes arguments another ignores.

    ``browser_headless`` is read only by the ``login`` verb. Manual login
    must always open a visible browser, so the orchestrator ignores this
    flag on that path; it is kept in the shape for forward compatibility
    with other verbs that may prefer a headless browser.
    """

    verb: str = "validate"
    session_path: Path | None = None
    force: bool = False
    #: Named account the ``login`` verb registers in the pool. Ignored by
    #: ``validate`` and ``delete``; defaults to "default".
    name: str = "default"
    #: Wait loop for the interactive login flow. The agent consults this
    #: while the headed browser is still live; ``None`` ends the loop at
    #: the first valid-session signal.
    wait_for_confirmation: Callable[[], bool] | None = None
    #: Login verb: always ``False`` in practice — the manual-login path
    #: forces a visible browser regardless of this flag.
    browser_headless: bool = False


@dataclass(frozen=True)
class SessionResponse:
    """What a session verb produced.

    ``valid`` carries the auth verdict for ``validate`` (True when the
    profile is authenticated and usable) and the pool availability flag for
    ``check_health`` (True when at least one session in the pool is
    healthy and ready to accept requests; False when the pool is empty or
    every session is rate-limited/unauthenticated). ``message`` carries
    the human-readable outcome of any verb; ``deleted`` reports whether
    ``delete`` removed a profile. ``error`` names the reason a request could
    not be answered at all. ``profile_path`` carries the resolved profile
    directory after a successful ``login`` so callers that receive the
    response without reading the exception can still locate the persisted
    session. ``sessions`` carries the pool listing for ``list_sessions``;
    ``removed`` reports whether ``remove_session`` dropped a pool entry.
    """

    valid: bool = False
    message: str = ""
    deleted: bool = False
    error: str | None = None
    #: Resolved profile directory, set on a successful ``login``.
    profile_path: Path | str | None = None
    #: Pool listing in pool order, set by the ``list_sessions`` verb.
    sessions: SessionList | None = None
    #: True when ``remove_session`` dropped a pool entry.
    removed: bool = False
    #: Session count for the ``check_health`` verb (healthy / total).
    health_healthy: int | None = None
    health_total: int | None = None
    #: Reasoned verdict fields for health checks
    status: str | None = None
    reason: str | None = None
    recovery_action: str | None = None
    health_results: list[SessionHealthResult] | None = None


__all__ = [
    "HealthReason",
    "RotatorRequest",
    "RotatorResponse",
    "SessionHealthResult",
    "SessionInfo",
    "SessionList",
    "SessionPool",
    "SessionRequest",
    "SessionResponse",
    "SessionStatus",
    "SessionId",
    "SessionName",
    "SessionReason",
]
