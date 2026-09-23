"""Session protocol contracts — multi-account rotation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from modules.shared.src.taxonomy_session_vo import SessionId, SessionInfo, SessionPool


class ISessionManagerProtocol(ABC):
    """Protocol for session storage and management."""

    @abstractmethod
    def load_pool(self) -> SessionPool:
        """Load session pool from disk."""

    @abstractmethod
    def save_pool(self, pool: SessionPool) -> None:
        """Persist session pool to disk."""

    @abstractmethod
    def add_session(self, name: str, profile_path: Path) -> SessionInfo:
        """Create and save a new session."""

    @abstractmethod
    def remove_session(self, session_id: str) -> bool:
        """Remove a session by ID."""

    @abstractmethod
    def list_sessions(self) -> list[SessionInfo]:
        """List all sessions."""


class ISessionHealthCheckerProtocol(ABC):
    """Protocol for session health checking via ping test."""

    @abstractmethod
    async def check_session(self, session: SessionInfo) -> bool:
        """Check if session is healthy. Returns True if OK, False if limited."""

    @abstractmethod
    async def check_all_sessions(self, pool: SessionPool) -> SessionPool:
        """Health check all sessions and return updated pool."""


class ISessionRotatorProtocol(ABC):
    """Protocol for transparent session rotation."""

    @abstractmethod
    async def get_next_session(self) -> SessionInfo | None:
        """Get next healthy session."""

    @abstractmethod
    async def mark_limited(self, session_id: str) -> None:
        """Mark session as rate-limited."""

    @abstractmethod
    async def mark_healthy(self, session_id: str) -> None:
        """Mark session as healthy."""


__all__ = [
    "ISessionManagerProtocol",
    "ISessionHealthCheckerProtocol",
    "ISessionRotatorProtocol",
]
