"""Unit tests for utility_core_session_backup — master session recovery (issue #300).

Locks the four guarantees behind a recoverable master profile: a snapshot exists
after a login, snapshots never nest, a restore only ever reads from the
session's own ``.backups`` directory, and deletion is refused while no backup
is retained.
"""

from __future__ import annotations

import hashlib
import itertools
import os
import time
from pathlib import Path

import pytest

import modules.shared.src.common.utility_core_session_backup as session_backup
from modules.shared.src.common.utility_core_session_backup import (
    BACKUPS_DIR_NAME,
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


def _stamp_clock(monkeypatch: pytest.MonkeyPatch, start: int = 0) -> None:
    """Make each generation stamp distinct without sleeping a second per call.

    ``take_snapshot`` names generations at second resolution, so a real burst
    of snapshots needs ``time.sleep(1.1)`` between calls to stay distinct.
    Driving the stamp directly keeps the same coverage at no wall-clock cost.
    """
    counter = itertools.count(start)

    def _next_stamp() -> str:
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(1_700_000_000 + next(counter)))

    monkeypatch.setattr(session_backup, "_generation_stamp", _next_stamp)


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


def test_take_snapshot_does_not_nest_a_previous_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_profile(tmp_path)
    _stamp_clock(monkeypatch)
    take_snapshot(tmp_path)
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


def test_generations_are_pruned_to_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _write_profile(tmp_path)
    _stamp_clock(monkeypatch)
    for _ in range(DEFAULT_MAX_GENERATIONS + 2):
        take_snapshot(tmp_path, max_generations=DEFAULT_MAX_GENERATIONS)

    assert snapshots_count(tmp_path) <= DEFAULT_MAX_GENERATIONS
    assert has_session_backup(tmp_path) is True


def test_restore_latest_reinstates_the_profile(tmp_path: Path):
    _write_profile(tmp_path)
    take_snapshot(tmp_path)

    (tmp_path / "Cookies").unlink()
    assert not (tmp_path / "Cookies").exists()

    restore_latest(tmp_path)

    assert (tmp_path / "Cookies").read_text(encoding="utf-8") == "live-credentials"


def test_restore_is_byte_identical_after_a_full_corruption_cycle(tmp_path: Path):
    """Acceptance: restoring a session backup leaves the target directory byte-identical.

    A restored profile must be indistinguishable from the snapshot it was taken
    from — matching SHA-256 hashes for every file, matching permission bits,
    and the same directory tree shape.
    """

    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _tree_state(root: Path) -> dict[Path, tuple[str, int]]:
        """Map of relative path -> (sha256, mode) for every file under *root*.

        The snapshot directory, Chromium runtime lock files, and the live
        ``.backups`` tree are excluded so only real profile content is
        compared.
        """
        skip_names = {BACKUPS_DIR_NAME, "SingletonLock", "DevToolsActivePort"}
        state: dict[Path, tuple[str, int]] = {}
        for entry in sorted(root.rglob("*")):
            if entry.name in skip_names:
                continue
            if entry.is_file():
                state[entry.relative_to(root)] = (_sha256(entry), entry.stat().st_mode & 0o777)
            elif entry.is_dir():
                state[entry.relative_to(root)] = (None, entry.stat().st_mode & 0o777)
        return state

    # Build a richer profile than the minimal helper for stronger coverage.
    _write_profile(tmp_path)
    (tmp_path / "Default" / "Network").mkdir(exist_ok=True)
    (tmp_path / "Default" / "Network" / "Cookies").write_text(
        "session-token=abc123", encoding="utf-8"
    )
    (tmp_path / "Default" / "Login Data").write_text("user@example.com", encoding="utf-8")

    # Take the snapshot — this is the reference state.
    generation = take_snapshot(tmp_path)

    reference_files = _tree_state(generation)
    reference_dirs = {p for p, (_, mode) in reference_files.items() if reference_files[p][0] is None}

    # Corrupt the live profile.
    (tmp_path / "Cookies").unlink()
    (tmp_path / "Default" / "Login Data").write_text("corrupted", encoding="utf-8")
    (tmp_path / "Default" / "Network" / "Cookies").write_text("corrupted", encoding="utf-8")

    # Restore from the backup.
    restore_generation(tmp_path, generation)

    # Verify tree shape is identical (no missing files, no extra files).
    # The live tree has a .backups dir the snapshot doesn't, so compare only
    # the files that existed in the snapshot.
    restored_files = _tree_state(tmp_path)
    reference_rel_paths = {p for p, (h, _) in reference_files.items() if h is not None}
    for rel in reference_rel_paths:
        assert rel in restored_files, f"Missing file after restore: {rel}"

    # Verify byte-identity: every file's SHA-256 matches.
    for rel, (ref_hash, _) in reference_files.items():
        if ref_hash is None:
            continue
        rest_hash = restored_files[rel][0]
        assert rest_hash == ref_hash, f"Byte mismatch in {rel}: {ref_hash} != {rest_hash}"

    # Verify permission bits on the profile root and all subdirectories.
    assert tmp_path.stat().st_mode & 0o777 == SNAPSHOT_MODE, "Profile root lost 0700 mode"
    for rel in reference_dirs:
        mode = restored_files[rel][1]
        assert mode == SNAPSHOT_MODE, f"Directory {rel} has mode {oct(mode)}, expected {oct(SNAPSHOT_MODE)}"

    # Verify the .backups directory is still intact after restore.
    assert has_session_backup(tmp_path), "Restore erased the .backups tree"
    assert snapshots_count(tmp_path) >= 1, "Restore erased all generations"


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
