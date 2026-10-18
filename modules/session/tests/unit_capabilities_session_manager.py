"""Unit tests for SessionManager.load_pool() profile auto-discovery.

A missing or stale ``sessions.json`` must not force the user to re-login
when Chromium profile directories already exist on disk: ``load_pool``
scans ``SESSIONS_DIR`` for profile-shaped subdirectories (``Default``
with a ``Cookies`` file, or a ``Local State`` file) and registers the
missing ones as ``SessionStatus.AUTH_REQUIRED`` (``UNKNOWN`` remains a
deprecated read-only alias for legacy pool files).
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.session.src.capabilities_session_health_checker import SessionHealthChecker
from modules.session.src.capabilities_session_manager import SessionManager
from modules.shared.src.common import taxonomy_core_constant as constants
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.session.taxonomy_session_vo import (
    SessionInfo,
    SessionPool,
    SessionStatus,
)

MODULE = "modules.session.src.capabilities_session_manager"


def _make_profile(root: Path, name: str) -> Path:
    """Create a Chromium-shaped profile directory under *root*."""
    profile = root / name
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("cookiejar", encoding="utf-8")
    (profile / "Local State").write_text("{}", encoding="utf-8")
    return profile


@pytest.fixture()
def patch_session_paths(tmp_path: Path):
    """Point POOL_FILE and SESSIONS_DIR at *tmp_path* for one test."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    with (
        patch(f"{MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MODULE}.POOL_FILE", pool_file),
    ):
        yield sessions_dir, pool_file


@pytest.fixture()
def manager(patch_session_paths) -> SessionManager:
    return SessionManager(base_dir=patch_session_paths[0])


def test_load_pool_missing_pool_file_discovers_profiles(
    manager: SessionManager, patch_session_paths: tuple[Path, Path]
) -> None:
    """N profile dirs with no sessions.json → N sessions and a persisted pool."""
    sessions_dir, pool_file = patch_session_paths
    assert not pool_file.exists()
    _make_profile(sessions_dir, "default")
    _make_profile(sessions_dir, "arwaky007")

    pool = manager.load_pool()

    assert pool.total_count == 2
    assert {s.name for s in pool.sessions} == {"default", "arwaky007"}
    assert all(s.status == SessionStatus.AUTH_REQUIRED for s in pool.sessions)
    assert pool_file.exists()
    data = json.loads(pool_file.read_text())
    assert len(data["sessions"]) == 2


def test_load_pool_missing_pool_file_no_profiles(tmp_path: Path) -> None:
    """No pool file and no profile dirs → empty pool, nothing written."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    pool_file = sessions_dir / "sessions.json"
    with (
        patch(f"{MODULE}.SESSIONS_DIR", sessions_dir),
        patch(f"{MODULE}.POOL_FILE", pool_file),
    ):
        manager = SessionManager(base_dir=sessions_dir)
        pool = manager.load_pool()

    assert pool.total_count == 0


def test_load_pool_writes_registry_only_when_missing_or_updated(
    manager: SessionManager, patch_session_paths: tuple[Path, Path]
) -> None:
    """A fresh no-profiles pool (file still absent) does not create sessions.json,
    while the first discovery pass does persist the registry."""
    sessions_dir, pool_file = patch_session_paths
    assert not pool_file.exists()
    manager.load_pool()
    assert not pool_file.exists()

    _make_profile(sessions_dir, "default")
    pool = manager.load_pool()
    assert pool.total_count == 1
    assert pool_file.exists()


def test_load_pool_existing_file_new_profile_dir_on_disk(
    manager: SessionManager, patch_session_paths: tuple[Path, Path]
) -> None:
    """A profile dir added after the pool was saved gets discovered on load."""
    sessions_dir, pool_file = patch_session_paths
    known = _make_profile(sessions_dir, "default")
    _make_profile(sessions_dir, "manual")

    manager.add_session("default", known)

    pool = manager.load_pool()

    names = {s.name for s in pool.sessions}
    assert names == {"default", "manual"}
    manual = next(s for s in pool.sessions if s.name == "manual")
    assert manual.status == SessionStatus.AUTH_REQUIRED


def test_load_pool_existing_file_matching_dirs_no_change(
    manager: SessionManager, patch_session_paths: tuple[Path, Path]
) -> None:
    """When the file and disk agree, load_pool adds nothing and rewrites nothing new."""
    sessions_dir, pool_file = patch_session_paths
    default = _make_profile(sessions_dir, "default")
    manager.add_session("default", default)
    sessions_before = json.loads(pool_file.read_text())["sessions"]

    pool = manager.load_pool()

    assert pool.total_count == 1
    assert pool.sessions[0].path == default
    assert pool.sessions[0].status == SessionStatus.AUTH_REQUIRED
    sessions_after = json.loads(pool_file.read_text())["sessions"]
    assert sessions_after == sessions_before


def test_load_pool_legacy_unknown_status_maps_to_auth_required(
    manager: SessionManager, patch_session_paths: tuple[Path, Path]
) -> None:
    """A legacy pool file writing ``"status": "unknown"`` loads as AUTH_REQUIRED
    with the stored reason intact (SessionStatus._missing_ read hook)."""
    sessions_dir, pool_file = patch_session_paths
    default = _make_profile(sessions_dir, "default")
    manager.add_session("default", default)
    data = json.loads(pool_file.read_text())
    data["sessions"][0]["status"] = "unknown"
    data["sessions"][0]["reason"] = "LEGACY"
    pool_file.write_text(json.dumps(data))

    pool = manager.load_pool()

    session = pool.sessions[0]
    assert session.status == SessionStatus.AUTH_REQUIRED
    assert session.reason == "LEGACY"


def test_load_pool_ignores_non_profile_dirs(manager: SessionManager, patch_session_paths: tuple[Path, Path]) -> None:
    """Subdirectories without Cookies or Local State are not profiles."""
    sessions_dir, _ = patch_session_paths
    _make_profile(sessions_dir, "default")
    stray = sessions_dir / "notes"
    stray.mkdir()
    (stray / "readme.txt").write_text("not a profile", encoding="utf-8")

    pool = manager.load_pool()

    assert pool.total_count == 1
    assert pool.sessions[0].name == "default"

def pool_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point POOL_FILE and SESSIONS_DIR at a tmp tree so no real profile is touched."""
    sessions_dir = tmp_path / "share" / "sessions"
    sessions_dir.mkdir(parents=True)
    monkeypatch.setattr(constants, "POOL_FILE", sessions_dir / "sessions.json")
    monkeypatch.setattr(constants, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr("modules.session.src.capabilities_session_manager.POOL_FILE", sessions_dir / "sessions.json")
    monkeypatch.setattr("modules.session.src.capabilities_session_manager.SESSIONS_DIR", sessions_dir)
    return sessions_dir


def _write_pool(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _profile(sessions_dir: Path, name: str) -> Path:
    profile = sessions_dir / name
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    (profile / "Default" / "Cookies").write_bytes(b"cookie")
    return profile


def _pool_entry(session_id: str, name: str, path: Path) -> dict[str, object]:
    return {
        "session_id": session_id,
        "name": name,
        "path": str(path),
        "status": "active",
        "last_used": None,
        "total_requests": 0,
        "failed_requests": 0,
        "created_at": "2026-01-01T00:00:00+00:00",
    }


# ── corrupt pool file: quarantine + rebuild (BE-2-002, D5) ─────────────────


def test_truncated_pool_json_is_quarantined_and_rebuilt(pool_home: Path) -> None:
    """A torn write leaves a partial file; it must not brick the feature."""
    profile = _profile(pool_home, "alpha")
    pool_path = pool_home / "sessions.json"
    _write_pool(pool_path, {"sessions": [_pool_entry("session_1", "alpha", profile)], "current_index": 0})
    # Truncate mid- JSON, like a crash during save_pool.
    truncated = pool_path.read_text(encoding="utf-8")[: len(pool_path.read_text(encoding="utf-8")) // 2]
    pool_path.write_text(truncated, encoding="utf-8")

    manager = SessionManager()
    pool = manager.load_pool()

    quarantined = list(pool_home.glob("sessions.json.corrupt-*"))
    assert len(quarantined) == 1, "the corrupt file must be quarantined with a timestamp suffix"
    assert not pool_path.exists() or pool_path.read_text(encoding="utf-8") != truncated
    assert len(pool.sessions) == 1, "the pool is rebuilt from the on-disk profile directories"
    assert pool.sessions[0].path == profile


def test_pool_json_missing_keys_is_quarantined_and_rebuilt(pool_home: Path) -> None:
    """A schema-invalid row (missing required keys) is handled the same way."""
    profile = _profile(pool_home, "alpha")
    pool_path = pool_home / "sessions.json"
    _write_pool(
        pool_path,
        {"sessions": [{"session_id": "session_1"}], "current_index": 0},  # missing name/path/status
    )

    manager = SessionManager()
    pool = manager.load_pool()

    assert len(list(pool_home.glob("sessions.json.corrupt-*"))) == 1
    assert [s.name for s in pool.sessions] == ["alpha"]
    assert pool.sessions[0].path == profile


def test_quarantine_warning_names_the_paths(pool_home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The operator gets a warning naming the pool path and the quarantine target."""
    _profile(pool_home, "alpha")
    (pool_home / "sessions.json").write_text("{not json", encoding="utf-8")

    with caplog.at_level("WARNING", logger="session_manager"):
        SessionManager().load_pool()

    warnings = [r for r in caplog.records if "session_pool_corrupt" in r.getMessage()]
    assert warnings, "a corrupt pool must log session_pool_corrupt"
    message = warnings[0].getMessage()
    assert "sessions.json" in message
    assert "corrupt-" in message


def test_save_pool_is_atomic_failure_leaves_the_old_file(pool_home: Path) -> None:
    """A failed save (here: an unwritable tmp swap) keeps the previous pool."""
    manager = SessionManager()
    pool = SessionPool(
        sessions=[
            SessionInfo(
                session_id="session_1",
                name="alpha",
                path=pool_home / "alpha",
                status=SessionStatus.ACTIVE,
                created_at=datetime(2026, 1, 1),
            )
        ]
    )
    manager.save_pool(pool)
    original = (pool_home / "sessions.json").read_text(encoding="utf-8")

    import unittest.mock as mock

    with mock.patch("modules.session.src.capabilities_session_manager.POOL_FILE") as mocked_path:
        mocked_path.with_name.return_value = pool_home / "sessions.json.tmp"
        mocked_path.name = "sessions.json"
        with mock.patch(
            "modules.session.src.capabilities_session_manager.os.replace", side_effect=OSError(28, "No space")
        ):
            with pytest.raises(OSError):
                manager.save_pool(pool)

    assert (pool_home / "sessions.json").read_text(encoding="utf-8") == original
    assert not (pool_home / "sessions.json.tmp").exists(), "the tmp swap must be cleaned up"


# ── session-ID uniqueness (BE-2-003) ─────────────────────────────────


def test_add_session_after_removal_generates_a_unique_id(pool_home: Path) -> None:
    """Removing a middle entry then adding must not collide with a surviving ID."""
    manager = SessionManager()
    for label in ("a", "b", "c"):
        manager.add_session(label, pool_home / label)

    assert manager.remove_session("session_2") is True

    info = manager.add_session("d", pool_home / "d")
    ids = [s.session_id for s in manager.load_pool().sessions]

    assert len(ids) == len(set(ids)), f"duplicate session IDs: {ids}"
    assert info.session_id not in {"session_1", "session_3"}


def test_discovered_profile_ids_do_not_collide_with_existing(pool_home: Path) -> None:
    """Auto-discovered IDs derive from the max numeric suffix, not pool length."""
    manager = SessionManager()
    manager.add_session("alpha", pool_home / "alpha")
    manager.add_session("beta", pool_home / "beta")
    manager.add_session("gamma", pool_home / "gamma")
    assert manager.remove_session("session_2") is True

    # A new on-disk profile the pool does not know about yet.
    _profile(pool_home, "delta")

    pool = manager.load_pool()
    ids = [s.session_id for s in pool.sessions]

    assert len(ids) == len(set(ids)), f"duplicate session IDs: {ids}"
    assert "delta" in [s.name for s in pool.sessions]


# ── legacy migration idempotency (BE-5-003) ─────────────────────────────────


def test_running_init_twice_keeps_a_populated_default_profile(pool_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-running the manager constructor must not destroy a populated profile."""
    legacy_root = pool_home / "legacy"
    legacy_default = legacy_root / "default"
    (legacy_default / "Default").mkdir(parents=True)
    (legacy_default / "Default" / "Cookies").write_bytes(b"token")

    monkeypatch.setattr(constants, "DEFAULT_SESSION_OLD", legacy_default)
    monkeypatch.setattr("modules.session.src.capabilities_session_manager.DEFAULT_SESSION_OLD", legacy_default)

    SessionManager()
    first_pass = (pool_home / "default" / "Default" / "Cookies").read_bytes()
    assert first_pass == b"token"
    assert not legacy_default.exists()

    SessionManager()
    second_pass = (pool_home / "default" / "Default" / "Cookies").read_bytes()

    assert second_pass == b"token", "the populated default/ profile survives a second init"
    assert not (pool_home / "default" / "default").exists(), "no nested duplicate profile"


# ── check_pool_sync probes run concurrently (BE-4-001) ─────────────────────────


class _SlowChecker(SessionHealthChecker):
    """A checker whose probes each sleep, so concurrency is measurable."""

    probe_duration: float = 0.15

    async def check_session(self, session: SessionInfo) -> bool:
        await asyncio.sleep(self.probe_duration)
        return session.status == SessionStatus.ACTIVE


def test_check_pool_sync_probes_run_concurrently(pool_home: Path) -> None:
    """N slow probes finish in about one probe duration, not N×."""
    sessions = [
        SessionInfo(
            session_id=f"session_{i}",
            name=f"pool-{i}",
            path=pool_home / f"pool-{i}",
            status=SessionStatus.ACTIVE,
            created_at=datetime(2026, 1, 1),
        )
        for i in range(4)
    ]
    pool = SessionPool(sessions=sessions)
    manager = MagicMock()
    checker = _SlowChecker()

    started = time.monotonic()
    results = checker.check_pool_sync(pool, manager)
    elapsed = time.monotonic() - started

    assert [s.session_id for s, _ in results] == [s.session_id for s in sessions]
    assert all(healthy is True for _, healthy in results)
    # 4 sequential probes would take >= 0.6s; concurrent must stay near one probe.
    assert elapsed < _SlowChecker.probe_duration * 2, f"probes ran sequentially: {elapsed:.2f}s"
    assert manager.mark_healthy.call_count == 4


def test_check_pool_sync_marks_limited_sessions_in_pool_order(pool_home: Path) -> None:
    """Manager state updates follow pool order even when probes gather concurrently."""
    sessions = [
        SessionInfo(
            session_id=f"session_{i}",
            name=f"pool-{i}",
            path=pool_home / f"pool-{i}",
            status=SessionStatus.LIMITED if i % 2 else SessionStatus.ACTIVE,
            created_at=datetime(2026, 1, 1),
        )
        for i in range(3)
    ]
    pool = SessionPool(sessions=sessions)
    manager = MagicMock()
    checker = _SlowChecker()

    results = checker.check_pool_sync(pool, manager)

    assert [healthy for _, healthy in results] == [True, False, True]
    marked = [call.args[0] for call in manager.mark_healthy.call_args_list]
    limited = [call.args[0] for call in manager.mark_limited.call_args_list]
    assert marked == ["session_0", "session_2"]
    assert limited == ["session_1"]


# ── unknown verb / lockfile hygiene ─────────────────────────────────


def test_pool_file_survives_an_empty_sessions_listing(pool_home: Path) -> None:
    """An absent pool file and no profiles yields an empty pool, not an error."""
    pool = SessionManager().load_pool()

    assert pool.sessions == []
    assert not (pool_home / "sessions.json").exists()

def _safe_profile(root: Path) -> Path:
    """A profile directory that clears the path-safety guard."""
    session = root / "share" / "sessions" / "default"
    (session / "Default").mkdir(parents=True)
    (session / "Default" / "Cookies").write_bytes(b"cookie")
    return session


def _orchestrator_target(sessions_dir: Path) -> tuple[SessionManager, Path]:
    target = _safe_profile(sessions_dir)
    manager = SessionManager()
    return manager, target


@pytest.fixture
def guarded_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[SessionManager, Path]:
    """A deletable profile with the guard's seams pointed at a tmp tree."""
    monkeypatch.setattr(
        "modules.shared.src.session.utility_session_guard.SESSIONS_DIR",
        tmp_path / "share" / "sessions",
    )
    monkeypatch.setattr(
        "modules.shared.src.common.taxonomy_core_constant.SESSIONS_DIR",
        tmp_path / "share" / "sessions",
    )
    return _orchestrator_target(tmp_path)


@pytest.mark.parametrize(
    ("exc", "label"),
    [
        (PermissionError("no backup retained"), "permission-refusal"),
        (OSError(28, "No space left on device"), "enospc"),
        (OSError(30, "Read-only file system"), "read-only-fs"),
    ],
)
def test_backup_guard_failure_refuses_deletion_and_keeps_profile(
    guarded_profile: tuple[SessionManager, Path],
    exc: BaseException,
    label: str,
) -> None:
    """Any guard failure must refuse the deletion, not remove the profile."""
    manager, target = guarded_profile

    with (
        patch("modules.session.src.capabilities_session_manager.shutil.rmtree") as rmtree,
        patch(
            "modules.session.src.capabilities_session_manager.utility_core_session_backup.refuse_delete_without_backup",
            side_effect=exc,
        ) as guard,
    ):
        with pytest.raises(QwenCliError, match="backup guard failed") as info:
            manager.delete_session_profile(target)

    assert str(target) in str(info.value), "the refusal must name the target path"
    guard.assert_called_once_with(target.resolve(), force=False)
    rmtree.assert_not_called()
    assert target.is_dir(), "the profile directory must survive the refusal"
    assert (target / "Default" / "Cookies").read_bytes() == b"cookie"
    assert label  # pins one row per failure class in the report


def test_backup_guard_refusal_message_names_the_target(
    guarded_profile: tuple[SessionManager, Path],
) -> None:
    """The QwenCliError message names the refused target (issue #300)."""
    manager, target = guarded_profile

    with patch(
        "modules.session.src.capabilities_session_manager.utility_core_session_backup.refuse_delete_without_backup",
        side_effect=PermissionError("Refusing to delete X: no session backup"),
    ):
        with pytest.raises(QwenCliError) as info:
            manager.delete_session_profile(target)

    assert str(target.resolve()) in str(info.value)


def test_forced_delete_bypasses_the_guard_and_logs_the_bypass(
    guarded_profile: tuple[SessionManager, Path],
) -> None:
    """A forced deletion proceeds and leaves an audit-trail warning."""
    manager, target = guarded_profile

    with (
        patch(
            "modules.session.src.capabilities_session_manager.utility_core_session_backup.refuse_delete_without_backup"
        ) as guard,
        patch("modules.session.src.capabilities_session_manager.log") as log,
    ):
        manager.delete_session_profile(target, force=True)

    guard.assert_called_once_with(target.resolve(), force=True)
    log.warning.assert_called_once()
    assert "session_delete_forced_backup_guard_bypassed" in log.warning.call_args.args[0]
    assert not target.exists(), "a forced deletion is the operator's explicit choice"


def test_missing_target_is_a_no_op_not_an_error(guarded_profile: tuple[SessionManager, Path]) -> None:
    """An already-absent profile is reported as deleted, not as an error."""
    manager, _ = guarded_profile
    manager.delete_session_profile(Path("/nonexistent/qwen-session"))
    # No exception is the assertion.


def test_session_directory_stays_owner_only_after_a_refused_delete(
    guarded_profile: tuple[SessionManager, Path],
) -> None:
    """A refused deletion must not relax the profile's permissions."""
    manager, target = guarded_profile
    os.chmod(target, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    with patch(
        "modules.session.src.capabilities_session_manager.utility_core_session_backup.refuse_delete_without_backup",
        side_effect=OSError(28, "No space left on device"),
    ):
        with pytest.raises(QwenCliError):
            manager.delete_session_profile(target)

    assert stat.S_IMODE(target.stat().st_mode) & 0o077 == 0

