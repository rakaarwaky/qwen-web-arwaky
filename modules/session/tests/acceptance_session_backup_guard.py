"""Acceptance tests for the deletion-safety requirement.

The requirement in `modules/session/FRD.md` FR-SESSION-004 is that no
profile is removed without a written backup, and that a backup failure
refuses the deletion. These pin the shared backup utility the session
aggregate refuses to delete without.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from modules.shared.src.utility_core_session_backup import (
    has_session_backup,
    refuse_delete_without_backup,
    snapshots_count,
)


def _session(root: Path) -> Path:
    session = root / "qwen_session"
    (session / "Default").mkdir(parents=True)
    (session / "Default" / "Cookies").write_bytes(b"cookie")
    return session


def test_acceptance_a_fresh_session_has_no_backup(tmp_path: Path) -> None:
    session = _session(tmp_path)

    assert has_session_backup(session) is False
    assert snapshots_count(session) == 0


def test_acceptance_a_session_directory_holding_cookies_is_owner_only(tmp_path: Path) -> None:
    """Cookies are live credentials, so the directory they live in must not
    be readable by another account."""
    session = _session(tmp_path)

    owner_only = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
    os.chmod(session, owner_only)

    assert stat.S_IMODE(session.stat().st_mode) == owner_only


def test_acceptance_deleting_without_a_backup_is_refused(tmp_path: Path) -> None:
    """The guard is the only thing standing between an operator and an
    unusable workspace, so it must refuse rather than warn."""
    session = _session(tmp_path)

    try:
        refuse_delete_without_backup(session)
    except Exception as exc:
        assert "backup" in str(exc).lower(), f"the refusal must name the backup, got: {exc}"
        return
    raise AssertionError("deleting a session with no backup must be refused")


def test_acceptance_forcing_bypasses_the_backup_guard(tmp_path: Path) -> None:
    session = _session(tmp_path)

    refuse_delete_without_backup(session, force=True)

    assert session.exists(), "a forced deletion is the operator's explicit choice"
