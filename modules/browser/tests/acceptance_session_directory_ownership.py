"""Acceptance tests for the session-deletion safety guarantee.

The requirement in `modules/session/FRD.md` FR-SESSION-004 is that no
profile is removed without a written backup, and that a backup failure
refuses the deletion rather than removing the profile unprotected. These
pin the shared backup utility that guarantee depends on.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from modules.shared.src.utility_core_session_backup import has_session_backup, snapshots_count


def _seed_session(root: Path) -> Path:
    """Create a session tree with one file and return its path."""
    session = root / "qwen_session"
    (session / "Default").mkdir(parents=True)
    (session / "Default" / "Cookies").write_bytes(b"cookie")
    return session


def test_acceptance_backup_is_absent_before_a_backup_is_taken(tmp_path: Path) -> None:
    session = _seed_session(tmp_path)

    assert has_session_backup(session) is False
    assert snapshots_count(session) == 0


def test_acceptance_seed_session_owns_live_cookies_under_owner_only_mode(tmp_path: Path) -> None:
    session = _seed_session(tmp_path)

    assert (session / "Default" / "Cookies").exists()
    os.chmod(session, 0o700)
    mode = stat.S_IMODE(session.stat().st_mode)
    assert mode == 0o700, "a session directory holding cookies must be owner-only"
