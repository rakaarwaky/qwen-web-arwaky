"""Unit tests for utility_core_session_backup — master session recovery (issue #300).

Locks the four guarantees behind a recoverable master profile: a snapshot exists
after a login, snapshots never nest, a restore only ever reads from the
session's own ``.backups`` directory, and deletion is refused while no backup
is retained.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from modules.shared.src.utility_core_session_backup import (
    DEFAULT_MAX_GENERATIONS,
    SNAPSHOT_MODE,
    backups_dir,
    has_session_backup,
    list_session_backups,
    refuse_delete_without_backup,
    restore_generation,
    restore_latest,
    snapshots_count,
    take_snapshot,
)


def _write_profile(session_path: Path) -> None:
    """Create a minimal Chromium-like profile with a cookie store."""
    session_path.mkdir(parents=True, exist_ok=True)
    (session_path / "Cookies").write_text("live-credentials", encoding="utf-8")
    (session_path / "Default").mkdir(exist_ok=True)
    (session_path / "Default" / "Preferences").write_text("{}", encoding="utf-8")


def test_backups_dir_is_hidden_under_the_session(tmp_path: Path):
    assert backups_dir(tmp_path).name == ".backups"
    assert backups_dir(tmp_path).parent == tmp_path


def test_no_backup_reported_for_a_fresh_session(tmp_path: Path):
    _write_profile(tmp_path)
    assert has_session_backup(tmp_path) is False
    assert snapshots_count(tmp_path) == 0
    assert list_session_backups(tmp_path) == []


def test_take_snapshot_copies_the_profile(tmp_path: Path):
    _write_profile(tmp_path)
    generation = take_snapshot(tmp_path)

    assert generation.is_dir()
    assert (generation / "Cookies").read_text(encoding="utf-8") == "live-credentials"
    assert (generation / "Default" / "Preferences").exists()
    assert has_session_backup(tmp_path) is True


def test_take_snapshot_does_not_nest_a_previous_generation(tmp_path: Path):
    _write_profile(tmp_path)
    take_snapshot(tmp_path)
    time.sleep(1.1)
    second = take_snapshot(tmp_path)

    assert not (second / ".backups").exists()
    assert not (second / ".backups" / ".backups").exists()


def test_take_snapshot_ignores_chromium_runtime_lock_files(tmp_path: Path):
    _write_profile(tmp_path)
    (tmp_path / "SingletonLock").write_text("", encoding="utf-8")
    (tmp_path / "DevToolsActivePort").write_text("12345", encoding="utf-8")

    generation = take_snapshot(tmp_path)

    assert not (generation / "SingletonLock").exists()
    assert not (generation / "DevToolsActivePort").exists()


def test_snapshot_is_hardened_because_the_profile_holds_credentials(tmp_path: Path):
    _write_profile(tmp_path)
    generation = take_snapshot(tmp_path)

    assert os.stat(generation).st_mode & 0o777 == SNAPSHOT_MODE


def test_generations_are_pruned_to_the_cap(tmp_path: Path):
    _write_profile(tmp_path)
    for _ in range(DEFAULT_MAX_GENERATIONS + 2):
        take_snapshot(tmp_path, max_generations=DEFAULT_MAX_GENERATIONS)
        time.sleep(1.1)

    assert snapshots_count(tmp_path) <= DEFAULT_MAX_GENERATIONS
    assert has_session_backup(tmp_path) is True


def test_restore_latest_reinstates_the_profile(tmp_path: Path):
    _write_profile(tmp_path)
    take_snapshot(tmp_path)

    (tmp_path / "Cookies").unlink()
    assert not (tmp_path / "Cookies").exists()

    restore_latest(tmp_path)

    assert (tmp_path / "Cookies").read_text(encoding="utf-8") == "live-credentials"


def test_restore_latest_refuses_when_no_generation_is_retained(tmp_path: Path):
    _write_profile(tmp_path)
    with pytest.raises(FileNotFoundError, match="login"):
        restore_latest(tmp_path)


def test_restore_refuses_a_generation_outside_the_backups_dir(tmp_path: Path):
    _write_profile(tmp_path)
    outsider = tmp_path / "not-a-generation"
    outsider.mkdir()

    with pytest.raises(ValueError, match="not under"):
        restore_generation(tmp_path, outsider)


def test_delete_is_refused_while_no_backup_is_retained(tmp_path: Path):
    _write_profile(tmp_path)
    with pytest.raises(PermissionError, match="CAPTCHA"):
        refuse_delete_without_backup(tmp_path)


def test_delete_is_permitted_once_a_backup_exists(tmp_path: Path):
    _write_profile(tmp_path)
    take_snapshot(tmp_path)
    refuse_delete_without_backup(tmp_path)


def test_delete_is_permitted_when_forced(tmp_path: Path):
    _write_profile(tmp_path)
    refuse_delete_without_backup(tmp_path, force=True)
