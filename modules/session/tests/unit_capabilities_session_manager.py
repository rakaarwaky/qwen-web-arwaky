"""Unit tests for SessionManager.load_pool() profile auto-discovery.

A missing or stale ``sessions.json`` must not force the user to re-login
when Chromium profile directories already exist on disk: ``load_pool``
scans ``SESSIONS_DIR`` for profile-shaped subdirectories (``Default``
with a ``Cookies`` file, or a ``Local State`` file) and registers the
missing ones as ``SessionStatus.UNKNOWN``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.session.src.capabilities_session_manager import SessionManager
from modules.shared.src.taxonomy_session_vo import SessionStatus

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
    assert all(s.status == SessionStatus.UNKNOWN for s in pool.sessions)
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
    assert manual.status == SessionStatus.UNKNOWN


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
    assert pool.sessions[0].status == SessionStatus.UNKNOWN
    sessions_after = json.loads(pool_file.read_text())["sessions"]
    assert sessions_after == sessions_before


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
