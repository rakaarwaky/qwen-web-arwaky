"""Session manager — persists and manages Qwen login sessions."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from modules.shared.src import utility_core_session_backup, utility_session_guard
from modules.shared.src.contract_session_protocol import ISessionManagerProtocol
from modules.shared.src.taxonomy_core_constant import POOL_FILE, SESSIONS_DIR
from modules.shared.src.taxonomy_core_error import QwenCliError
from modules.shared.src.taxonomy_session_vo import SessionInfo, SessionList, SessionPool, SessionStatus

if TYPE_CHECKING:
    pass


# Block 1: Class Definition & Constructor


class SessionManager(ISessionManagerProtocol):
    """Manages Qwen session storage and CRUD operations."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or SESSIONS_DIR
        self._ensure_dirs()

    # Block 2: Protocol Method Implementation

    def load_pool(self) -> SessionPool:
        """Load session pool from disk."""
        if not POOL_FILE.exists():
            return SessionPool.empty()

        data = json.loads(POOL_FILE.read_text())
        sessions = []
        for s in data.get("sessions", []):
            sessions.append(
                SessionInfo(
                    session_id=s["session_id"],
                    name=s["name"],
                    path=Path(s["path"]),
                    status=SessionStatus(s["status"]),
                    last_used=self._parse_datetime(s.get("last_used")),
                    total_requests=s.get("total_requests", 0),
                    failed_requests=s.get("failed_requests", 0),
                    created_at=self._parse_datetime(s["created_at"]) or datetime.now().astimezone(),
                )
            )
        return SessionPool(sessions=sessions, current_index=data.get("current_index", 0))

    def save_pool(self, pool: SessionPool) -> None:
        """Persist session pool to disk."""
        data: dict[str, object] = {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "name": s.name,
                    "path": str(s.path),
                    "status": s.status.value,
                    "last_used": s.last_used.isoformat() if s.last_used else None,
                    "total_requests": s.total_requests,
                    "failed_requests": s.failed_requests,
                    "created_at": s.created_at.isoformat(),
                }
                for s in pool.sessions
            ],
            "current_index": pool.current_index,
        }
        POOL_FILE.write_text(json.dumps(data, indent=2))

    def add_session(self, name: str, profile_path: Path) -> SessionInfo:
        """Create and save a new session."""
        session_id = f"session_{len(self.load_pool().sessions) + 1}"
        info = SessionInfo(
            session_id=session_id,
            name=name,
            path=profile_path,
            status=SessionStatus.UNKNOWN,
        )
        pool = self.load_pool()
        pool.add_session(info)
        self.save_pool(pool)
        return info

    def remove_session(self, session_id: str) -> bool:
        """Remove a session by ID."""
        pool = self.load_pool()
        if pool.remove_session(session_id):
            self.save_pool(pool)
            return True
        return False

    def delete_session_profile(self, profile_path: Path, *, force: bool = False) -> None:
        """Remove the saved Chromium profile directory at *profile_path*.

        Safety checks run before anything is removed: the target must exist,
        must clear ``is_safe_session_target`` (never a filesystem root, a
        near-root path, or a path outside the allow-list), and must have a
        retained backup generation unless *force* is set. A partial removal
        raises rather than silently leaving an inconsistent profile.
        """
        target = profile_path.resolve()
        if not target.exists():
            return
        if not utility_session_guard.is_safe_session_target(target):
            raise QwenCliError(f"Refusing to delete unsafe session path: {target}")
        try:
            utility_core_session_backup.refuse_delete_without_backup(target, force=force)
        except PermissionError as exc:
            raise QwenCliError(str(exc)) from exc
        try:
            shutil.rmtree(target)
        except Exception as exc:
            raise QwenCliError(
                f"Failed to delete session {target}: {exc}. "
                "Deletion may be partial — remove the remaining directory manually."
            ) from exc

    def list_sessions(self) -> SessionList:
        """List all sessions."""
        return SessionList(self.load_pool().sessions)

    def get_session(self, session_id: str) -> SessionInfo | None:
        """Get a session by ID."""
        return self.load_pool().get_session(session_id)

    def get_next_healthy_session(self) -> SessionInfo | None:
        """Get next healthy session for rotation."""
        return self.load_pool().get_next_session()

    def mark_limited(self, session_id: str) -> None:
        """Mark session as rate-limited."""
        pool = self.load_pool()
        pool.mark_limited(session_id)
        self.save_pool(pool)

    def mark_healthy(self, session_id: str) -> None:
        """Mark session as healthy."""
        pool = self.load_pool()
        pool.mark_healthy(session_id)
        self.save_pool(pool)

    # Block 3: Dunder Methods, Factories & Helpers

    def _ensure_dirs(self) -> None:
        """Create session storage directories."""
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _parse_datetime(iso_str: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        from datetime import datetime as _dt

        if not iso_str:
            return None
        try:
            return _dt.fromisoformat(iso_str)
        except ValueError:
            return None


__all__ = ["SessionManager"]
