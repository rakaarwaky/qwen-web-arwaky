"""ISSUE-001: workspace init must create session-bearing dirs as 0700."""

from __future__ import annotations

import stat
from pathlib import Path

from modules.config.src.capabilities_workspace_provisioner import WorkspaceProvisioner
from modules.shared.src.common.taxonomy_core_constant import DEFAULT_SESSION
from modules.shared.src.common.taxonomy_core_vo import FilePath


def test_init_workspace_hardens_session_dir(tmp_path: Path) -> None:
    WorkspaceProvisioner().init_workspace(FilePath(str(tmp_path / "ws")))
    assert DEFAULT_SESSION.is_dir()
    mode = stat.S_IMODE(DEFAULT_SESSION.stat().st_mode)
    assert mode & 0o077 == 0, f"session dir mode {oct(mode)} is not owner-only"
