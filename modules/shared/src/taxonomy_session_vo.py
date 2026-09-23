"""Session value objects — multi-account rate limit rotation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TypeAlias


class SessionStatus(str, Enum):
    """Health status of a Qwen session."""

    ACTIVE = "active"  # Healthy, can send requests
    LIMITED = "limited"  # Hit rate limit
    UNKNOWN = "unknown"  # Not tested yet


SessionId: TypeAlias = str
SessionName: TypeAlias = str


@dataclass(frozen=True)
class SessionInfo:
    """Immutable metadata about a single Qwen login session."""

    session_id: SessionId
    name: SessionName
    path: Path
    status: SessionStatus = SessionStatus.UNKNOWN
    last_used: datetime | None = field(default=None)
    total_requests: int = field(default=0)
    failed_requests: int = field(default=0)
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())

    @property
    def is_healthy(self) -> bool:
        """True if session can accept requests."""
        return self.status == SessionStatus.ACTIVE

    @property
    def is_limited(self) -> bool:
        """True if session has hit rate limit."""
        return self.status == SessionStatus.LIMITED

    @property
    def failure_rate(self) -> float:
        """Ratio of failed requests (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    def with_status(self, status: SessionStatus) -> "SessionInfo":
        """Return a copy with updated status."""
        return SessionInfo(
            session_id=self.session_id,
            name=self.name,
            path=self.path,
            status=status,
            last_used=self.last_used,
            total_requests=self.total_requests,
            failed_requests=self.failed_requests,
            created_at=self.created_at,
        )

    def with_usage(self, success: bool) -> "SessionInfo":
        """Return a copy with updated usage counters."""
        return SessionInfo(
            session_id=self.session_id,
            name=self.name,
            path=self.path,
            status=self.status,
            last_used=datetime.now().astimezone(),
            total_requests=self.total_requests + 1,
            failed_requests=self.failed_requests + (0 if success else 1),
            created_at=self.created_at,
        )


@dataclass
class SessionPool:
    """Mutable collection of sessions with rotation logic."""

    sessions: list[SessionInfo] = field(default_factory=list)
    current_index: int = 0

    @classmethod
    def empty(cls) -> "SessionPool":
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

    def mark_limited(self, session_id: str) -> None:
        """Mark a session as rate-limited."""
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                self.sessions[i] = s.with_status(SessionStatus.LIMITED)
                return

    def mark_healthy(self, session_id: str) -> None:
        """Mark a session as healthy after successful request."""
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                self.sessions[i] = s.with_status(SessionStatus.ACTIVE)
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


__all__ = [
    "SessionInfo",
    "SessionPool",
    "SessionStatus",
    "SessionId",
    "SessionName",
]
