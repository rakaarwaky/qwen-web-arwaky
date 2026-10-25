"""Unit tests for cross-user session-directory permission repair.

Covers SESSION-03 (FR-SESSION-004): when the browser launches a session
context under a different user, the session directory is repaired to
owner-only ``0o700`` if writable, or launch is refused with reason
``session_dir_cross_user`` when it is not.

The tests exercise ``SessionManager.repair_session_dir_permissions``
directly (not via the constructor) so they can monkeypatch the OS-level
calls without interfering with the migration logic that runs in
``_ensure_dirs``.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.session.src.capabilities_session_manager import SessionManager


def _fake_stat_result(mode: int, uid: int) -> os.stat_result:
    return os.stat_result((mode, 0, 0, 0, uid, 0, 0, 0, 0, 0))


def _manager(target: Path) -> SessionManager:
    """Return a manager for calling ``repair_session_dir_permissions`` on *target*.

    Constructed via ``__new__`` so the ``__init__`` / ``_ensure_dirs`` /
    ``_migrate_legacy_session`` chain is skipped entirely; only the target's
    ``_base_dir`` attribute is set. This keeps the tests focused on the
    public repair method in isolation.
    """
    manager = object.__new__(SessionManager)
    manager._base_dir = target
    return manager


def test_repair_cross_user_dir_with_write_access_hardens_to_0700(tmp_path: Path) -> None:
    target = tmp_path / "session"
    target.mkdir()
    target.chmod(0o755)

    fake_stat = _fake_stat_result(0o755, uid=999)
    with (
        patch.object(os, "getuid", return_value=1000),
        patch.object(Path, "stat", return_value=fake_stat),
        patch.object(Path, "chmod") as chmod,
        patch.object(os, "access", return_value=True),
    ):
        manager = _manager(target)
        manager.repair_session_dir_permissions(target)
        chmod.assert_called_once_with(0o700)


def test_repair_cross_user_dir_without_write_access_refuses(tmp_path: Path) -> None:
    target = tmp_path / "session"
    target.mkdir()
    target.chmod(0o755)

    fake_stat = _fake_stat_result(0o755, uid=999)
    with (
        patch.object(os, "getuid", return_value=1000),
        patch.object(Path, "stat", return_value=fake_stat),
        patch.object(Path, "chmod") as chmod,
        patch.object(os, "access", return_value=False),
    ):
        manager = _manager(target)
        with pytest.raises(Exception) as exc:
            manager.repair_session_dir_permissions(target)
        assert "session_dir_cross_user" in str(exc.value)
        chmod.assert_not_called()


def test_repair_same_user_dir_hardens_to_0700(tmp_path: Path) -> None:
    target = tmp_path / "session"
    target.mkdir()
    target.chmod(0o755)

    fake_stat = _fake_stat_result(0o755, uid=1000)
    with (
        patch.object(os, "getuid", return_value=1000),
        patch.object(Path, "stat", return_value=fake_stat),
        patch.object(Path, "chmod") as chmod,
        patch.object(os, "access", return_value=True),
    ):
        manager = _manager(target)
        manager.repair_session_dir_permissions(target)
        chmod.assert_called_once_with(0o700)
