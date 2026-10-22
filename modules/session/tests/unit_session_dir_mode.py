"""ISSUE-001: session storage directories must be owner-only 0700."""

from __future__ import annotations

import stat
from pathlib import Path

from modules.session.src.capabilities_session_manager import SessionManager


def test_session_base_dir_is_0700(tmp_path: Path) -> None:
    base = tmp_path / "sessions"
    SessionManager(base_dir=base)
    mode = stat.S_IMODE(base.stat().st_mode)
    assert mode & 0o077 == 0, f"session base dir mode {oct(mode)} is not owner-only"
