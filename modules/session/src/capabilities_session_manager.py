"""Session manager — persists and manages Qwen login sessions."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import modules.shared.src.session.utility_session_guard as utility_session_guard
from modules.shared.src.common import utility_core_session_backup
from modules.shared.src.common.taxonomy_core_constant import DEFAULT_SESSION_OLD, POOL_FILE, SESSIONS_DIR
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.common.utility_io_writer import exclusive_file_lock
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.session.contract_session_protocol import ISessionManagerProtocol
from modules.shared.src.session.taxonomy_session_vo import (
    SessionInfo,
    SessionList,
    SessionPool,
    SessionReason,
    SessionStatus,
)

log = get_logger("session_manager")


# Block 1: Class Definition & Constructor


class SessionManager(ISessionManagerProtocol):
    """Manages Qwen session storage and CRUD operations."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or SESSIONS_DIR
        self._ensure_dirs()

    # Block 2: Protocol Method Implementation

    def load_pool(self) -> SessionPool:
        """Load session pool from disk, auto-discovering profile dirs on disk.

        Missing Chromium profiles are registered so users who added a
        profile manually (or on another machine/tool) do not re-login.
        A discovery write re-takes the pool lock and reloads so it cannot
        clobber a concurrent locked mutation.
        """
        pool = self._load_pool_from_file()
        added = self._register_discovered_profiles(pool)
        if not added:
            return pool
        with self._pool_lock():
            return self._load_pool_under_lock()

    def _load_pool_under_lock(self) -> SessionPool:
        """Load and persist discoveries. Caller must already hold ``_pool_lock``."""
        pool = self._load_pool_from_file()
        if self._register_discovered_profiles(pool):
            self.save_pool(pool)
        return pool

    def _load_pool_from_file(self) -> SessionPool:
        """Load the session pool from POOL_FILE, or an empty pool when absent."""
        if not POOL_FILE.exists():
            return SessionPool.empty()

        try:
            raw = POOL_FILE.read_text()
        except OSError as exc:
            # A transient read failure (EMFILE etc.) is not corruption: surface
            # a named-path error instead of quarantining a healthy file.
            raise QwenCliError(f"Cannot read session pool at {POOL_FILE}: {exc}") from exc

        try:
            data = json.loads(raw)
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
                        reason=s.get("reason"),
                    )
                )
            return SessionPool(sessions=sessions, current_index=data.get("current_index", 0))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            ts = int(datetime.now().astimezone().timestamp())
            corrupt_file = POOL_FILE.with_name(f"{POOL_FILE.name}.corrupt-{ts}")
            with contextlib.suppress(OSError):
                os.replace(POOL_FILE, corrupt_file)
            log.warning("session_pool_corrupt path=%s quarantined_to=%s error=%s", POOL_FILE, corrupt_file, exc)
            return SessionPool.empty()

    @staticmethod
    def _next_session_id(existing_sessions: list[SessionInfo]) -> str:
        """Derive the next unique session_id from the max numeric suffix among existing IDs.

        ``max_num + 1`` is by construction the first integer past every
        existing numeric suffix, so it cannot collide with any surviving ID.
        """
        max_num = 0
        for s in existing_sessions:
            if s.session_id.startswith("session_"):
                suffix = s.session_id.removeprefix("session_")
                if suffix.isdigit():
                    max_num = max(max_num, int(suffix))
        return f"session_{max_num + 1}"

    def _register_discovered_profiles(self, pool: SessionPool) -> int:
        """Register profile dirs on disk missing from *pool*; returns the count added."""
        known = {s.path.resolve() for s in pool.sessions}
        added = 0
        for profile_dir in self._iter_profile_dirs():
            if profile_dir.resolve() in known:
                continue
            name = profile_dir.name
            session_id = self._next_session_id(pool.sessions)
            pool.add_session(
                SessionInfo(
                    session_id=session_id,
                    name=name,
                    path=profile_dir,
                    status=SessionStatus.AUTH_REQUIRED,
                )
            )
            known.add(profile_dir.resolve())
            added += 1
            log.info("auto_discovered_profile %s registered in session pool", profile_dir)
        return added

    @staticmethod
    def _iter_profile_dirs() -> list[Path]:
        """Yield subdirectories of SESSIONS_DIR that look like Chromium profiles.

        Symbolic links are skipped: a symlink placed in the sessions
        directory would adopt an arbitrary external profile.
        """
        if not SESSIONS_DIR.is_dir():
            return []
        profiles: list[Path] = []
        for child in sorted(SESSIONS_DIR.iterdir()):
            if child.is_symlink():
                continue
            if not child.is_dir():
                continue
            if (child / "Local State").is_file() or (child / "Default" / "Cookies").is_file():
                profiles.append(child)
        return profiles

    def save_pool(self, pool: SessionPool) -> None:
        """Persist session pool to disk atomically.

        The write itself stays a plain ``os.replace`` swap: callers that hold
        :meth:`_pool_lock` serialize the load→mutate→save cycle, so a
        concurrent writer (the MCP server and a CLI session command running
        at once) waits rather than overwriting the other's update.
        """
        data: dict[str, object] = {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "name": s.name,
                    "path": str(s.path),
                    "status": s.status.value,
                    "reason": s.reason,
                    "last_used": s.last_used.isoformat() if s.last_used else None,
                    "total_requests": s.total_requests,
                    "failed_requests": s.failed_requests,
                    "created_at": s.created_at.isoformat(),
                }
                for s in pool.sessions
            ],
            "current_index": pool.current_index,
        }
        # A unique tmp name per write (pid) so two concurrent writers in
        # different processes do not share a tmp target.
        tmp = POOL_FILE.with_name(f"{POOL_FILE.name}.{os.getpid()}.tmp")
        try:
            # 0o600 so a previously restrictive pool file does not become
            # world-readable after the swap.
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, json.dumps(data, indent=2).encode("utf-8"))
            finally:
                os.close(fd)
            os.replace(tmp, POOL_FILE)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def add_session(self, name: str, profile_path: Path) -> SessionInfo:
        """Create and save a new session, or update the existing entry with
        this profile path. Idempotent: when an entry with the same
        ``profile_path`` already exists, only its name is updated rather
        than adding a duplicate row.
        """
        with self._pool_lock():
            pool = self._load_pool_under_lock()
            for i, s in enumerate(pool.sessions):
                if s.path == profile_path:
                    # Frozen dataclass: replace the entry with a copy that has
                    # the new name instead of mutating in place.
                    pool.sessions[i] = s.with_name(name)
                    self.save_pool(pool)
                    return pool.sessions[i]
            session_id = self._next_session_id(pool.sessions)
            info = SessionInfo(
                session_id=session_id,
                name=name,
                path=profile_path,
                status=SessionStatus.AUTH_REQUIRED,
            )
            pool.add_session(info)
            self.save_pool(pool)
            return info

    def remove_session(self, session_id: str) -> bool:
        """Remove a session by ID."""
        with self._pool_lock():
            pool = self._load_pool_under_lock()
            if pool.remove_session(session_id):
                self.save_pool(pool)
                return True
        return False

    def get_session_by_name(self, name: str) -> SessionInfo | None:
        """Return the pool entry registered under *name*, or None when absent."""
        return next((s for s in self.load_pool().sessions if s.name == name), None)

    def remove_session_by_name(self, name: str) -> bool:
        """Remove the pool entry registered under *name*; True when found."""
        with self._pool_lock():
            pool = self._load_pool_under_lock()
            removed = False
            for i, s in enumerate(pool.sessions):
                if s.name == name:
                    pool.sessions.pop(i)
                    removed = True
                    break
            if removed:
                self.save_pool(pool)
        return removed

    def delete_session_profile(self, profile_path: Path, *, force: bool = False) -> bool:
        """Remove the saved Chromium profile directory at *profile_path*.

        Safety checks run before anything is removed: the target must exist,
        must clear ``is_safe_session_target`` (never a filesystem root, a
        near-root path, or a path outside the allow-list), and must have a
        retained backup generation unless *force* is set. A partial removal
        raises rather than silently leaving an inconsistent profile.

        Returns True when the profile was removed, False when the target
        did not exist (a no-op that the caller must not report as success).
        """
        target = profile_path.resolve()
        if not target.exists():
            return False
        if not utility_session_guard.is_safe_session_target(target):
            raise QwenCliError(f"Refusing to delete unsafe session path: {target}")
        if force:
            log.warning("session_delete_forced_backup_guard_bypassed target=%s", target)
        try:
            utility_core_session_backup.refuse_delete_without_backup(target, force=force)
        except OSError as exc:
            raise QwenCliError(f"Refusing to delete {target}: backup guard failed: {exc}") from exc
        try:
            shutil.rmtree(target)
        except Exception as exc:
            raise QwenCliError(
                f"Failed to delete session {target}: {exc}. "
                "Deletion may be partial — remove the remaining directory manually."
            ) from exc
        return True

    def find_pool_profile_with_content(self) -> Path | None:
        """Return the first pool session path holding real Chromium content.

        Pool entries are registered metadata, not a guarantee the profile
        directory still exists: a session can stay registered after its
        ``Local State`` / ``Default/Cookies`` files were removed. The first
        entry whose path is a directory carrying either marker file wins;
        ``None`` means the pool has no usable on-disk profile.
        """
        for s in self.load_pool().sessions:
            profile_dir = Path(s.path)
            if profile_dir.is_dir() and (
                (profile_dir / "Local State").is_file() or (profile_dir / "Default" / "Cookies").is_file()
            ):
                return profile_dir
        return None

    def list_sessions(self) -> SessionList:
        """List all sessions."""
        return SessionList(self.load_pool().sessions)

    def get_session(self, session_id: str) -> SessionInfo | None:
        """Get a session by ID."""
        return self.load_pool().get_session(session_id)

    def get_next_healthy_session(self) -> SessionInfo | None:
        """Get next healthy session for rotation."""
        return self.load_pool().get_next_session()

    def mark_limited(self, session_id: str, reason: SessionReason | None = "QUOTA") -> None:
        """Mark session as rate-limited; a ``None`` reason normalises to ``"QUOTA"``."""
        with self._pool_lock():
            pool = self._load_pool_under_lock()
            pool.mark_limited(session_id, reason=reason)
            self.save_pool(pool)

    def mark_healthy(self, session_id: str) -> None:
        """Mark session as healthy."""
        with self._pool_lock():
            pool = self._load_pool_under_lock()
            pool.mark_healthy(session_id)
            self.save_pool(pool)

    def mark_auth_required(self, session_id: str, reason: SessionReason | None = None) -> None:
        """Mark session as requiring authentication or setup."""
        with self._pool_lock():
            pool = self._load_pool_under_lock()
            pool.mark_auth_required(session_id, reason=reason)
            self.save_pool(pool)

    def mark_used(self, session_id: str, *, success: bool = True) -> None:
        """Record a completed request against the session under the pool lock."""
        with self._pool_lock():
            pool = self._load_pool_under_lock()
            pool.sessions = [s.with_usage(success=success) if s.session_id == session_id else s for s in pool.sessions]
            self.save_pool(pool)

    # Block 3: Dunder Methods, Factories & Helpers

    @contextlib.contextmanager
    def _pool_lock(self) -> Iterator[None]:
        """Serialize the load→mutate→save cycle against other processes.

        The pool file is shared by the long-lived MCP server and short-lived
        CLI session commands; without an exclusive advisory lock the two
        read-modify-write cycles would silently lose one writer's update.
        """
        with exclusive_file_lock(POOL_FILE.with_name(POOL_FILE.name + ".lock")):
            yield

    def _ensure_dirs(self) -> None:
        """Create session storage directories and migrate the legacy profile.

        Session dirs hold live login cookies, so they are owner-only 0700
        (ISSUE-001 / session FRD NFR). A cross-user-owned dir is repaired
        in place when writable, otherwise launch is refused before any
        browser process starts.
        """
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self.repair_session_dir_permissions(self._base_dir)
        self._migrate_legacy_session()

    def repair_session_dir_permissions(self, path: Path) -> None:
        """Repair cross-user ownership of *path* or refuse launch.

        Cross-user means ``st_uid != os.getuid()``:

        - same user: ensure owner-only ``0o700`` (harden).
        - cross-user with write access: repair in place via ``chmod(0o700)``.
        - cross-user without write access: refuse launch with reason
          ``session_dir_cross_user`` before any browser process starts.

        ``os.getuid``/``os.stat``/``os.chmod``/``os.access`` are used
        directly so tests can monkeypatch them without touching real uids.
        """
        try:
            st = path.stat()
        except OSError:
            return
        if st.st_uid != os.getuid():
            if not os.access(path, os.W_OK):
                msg = (
                    f"Refusing to launch: session directory owned by a "
                    f"different user and not writable: {path} "
                    f"(session_dir_cross_user)"
                )
                raise QwenCliError(msg)
            path.chmod(0o700)
            return
        path.chmod(0o700)

    def _migrate_legacy_session(self) -> None:
        """One-time move of the old single-profile dir into the new layout.

        If ``DEFAULT_SESSION_OLD`` (the pre-multi-account location) exists
        with content and ``DEFAULT_SESSION`` (the new per-account dir) is
        absent, move the profile. The move is safe: Chromium's user-data-dir
        is the same shape, only the parent changed. No re-auth required.
        """
        new_default = self._base_dir / "default"
        if new_default.is_dir() and any(new_default.iterdir()):
            return
        old_dir = DEFAULT_SESSION_OLD
        if not old_dir.is_dir() or not any(old_dir.iterdir()):
            return
        if new_default.is_dir() and not any(new_default.iterdir()):
            # Empty new dir exists (created by _ensure_dirs); merge old contents.
            for child in old_dir.iterdir():
                shutil.move(str(child), str(new_default / child.name))
            shutil.rmtree(old_dir, ignore_errors=True)
        else:
            shutil.move(str(old_dir), str(new_default))
        log.info(
            "legacy_session_migrated %s -> %s",
            old_dir,
            new_default,
        )

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
