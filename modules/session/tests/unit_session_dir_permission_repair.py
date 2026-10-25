"""Unit tests for cross-user session-directory permission repair.

Covers SESSION-03 (FR-SESSION-004): when the browser launches a session
context under a different user, the session directory is repaired to
owner-only ``0o700`` if writable, or launch is refused with reason
``session_dir_cross_user`` when it is not.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.session.src.capabilities_session_manager import SessionManager


def _fake_stat(mode: int, uid: int) -> os.stat_result:
    return os.stat_result((mode, 0, 0, 0, uid, 0, 0, 0, 0, 0))


def test_repair_cross_user_dir_with_write_access_hardens_to_0700(tmp_path: Path) -> None:
    target = tmp_path / "session"
    target.mkdir()

    fake_stat = _fake_stat(0o755, 999)
    with patch.object(os, "getuid", return_value=1000), patch.object(
        Path, "stat", return_value=fake_stat
    ), patch.object(Path, "chmod") as chmod, patch.object(os, "access", return_value=True):
        SessionManager(base_dir=target)
        chmod.assert_called_once_with(0o700)


def test_repair_cross_user_dir_without_write_access_refuses(tmp_path: Path) -> None:
    target = tmp_path / "session"
    target.mkdir()

    fake_stat = _fake_stat(0o755, 999)
    with patch.object(os, "getuid", return_value=1000), patch.object(
        Path, "stat", return_value=fake_stat
    ), patch.object(os, "access", return_value=False):
        with pytest.raises(Exception) as exc:
            SessionManager(base_dir=target)
        assert "session_dir_cross_user" in str(exc.value)


def test_repair_same_user_dir_hardens_to_0700(tmp_path: Path) -> None:
    target = tmp_path / "session"
    target.mkdir()

    fake_stat = _fake_stat(0o755, 1000)
    with patch.object(os, "getuid", return_value=1000), patch.object(
        Path, "stat", return_value=fake_stat
    ), patch.object(Path, "chmod") as chmod, patch.object(os, "access", return_value=True):
        SessionManager(base_dir=target)
        chmod.assert_called_once_with(0o700)
