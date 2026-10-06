"""Integration tests for config path resolution against the real filesystem.

These create real directories and files, so they exercise the writability
and existence probes the resolver runs, rather than a stub. No network and
no browser are involved.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.shared.src.taxonomy_core_vo import AppConfig


def _config(root: Path) -> AppConfig:
    """Return a config whose input and session paths already exist."""
    (root / "input.md").write_text("prompt", encoding="utf-8")
    (root / "session").mkdir()
    return AppConfig(
        mode="single",
        input_path=root / "input.md",
        output_path=root / "out.md",
        session_path=root / "session",
    )


def _by_role(resolved) -> dict[str, object]:
    return {item.role: item for item in resolved.paths}


def test_integration_a_not_yet_created_output_directory_is_accepted(tmp_path: Path) -> None:
    resolved = ConfigPathResolver().resolve_paths(_config(tmp_path))

    output = _by_role(resolved)["output_path"]
    assert output.exists is False
    assert output.writable is True, "a creatable output directory is usable"
    assert [issue.field for issue in resolved.issues] == []


def test_integration_an_existing_input_file_is_reported_as_existing(tmp_path: Path) -> None:
    resolved = ConfigPathResolver().resolve_paths(_config(tmp_path))

    assert _by_role(resolved)["input_path"].exists is True


def test_integration_a_read_only_output_directory_is_reported_as_unwritable(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        # root ignores the write bit, so the probe cannot observe the
        # refusal this test is about.
        return
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    os.chmod(readonly, stat.S_IRUSR | stat.S_IXUSR)
    config = _config(tmp_path)
    object.__setattr__(config, "output_path", readonly / "out.md")

    resolved = ConfigPathResolver().resolve_paths(config)

    assert "output_path" in {issue.field for issue in resolved.issues}
