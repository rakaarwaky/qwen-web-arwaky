"""Issue #279: rollback-status edge cases locked offline.

Covers the business rules the BA review surfaced — unknown previous version,
editable installs, and partial rollback reporting — without touching the
network or running a real pip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.shared.src.taxonomy_core_vo import VersionString
from modules.update.src import capabilities_update_rollback as rollback_module
from modules.update.src.capabilities_update_rollback import UpdateRollbackCapability
from modules.update.src.capabilities_update_upgrade import UpdateUpgradeCapability


def _rollback(
    tmp_path: Path | None = None, *, monkeypatch: pytest.MonkeyPatch | None = None
) -> UpdateRollbackCapability:
    upgrade = UpdateUpgradeCapability()
    rollback = UpdateRollbackCapability(upgrade, package_name="qwen-web-arwaky")
    if monkeypatch is not None and tmp_path is not None:
        monkeypatch.chdir(tmp_path)
    return rollback


def test_rollback_unknown_previous_version_returns_skipped_message() -> None:
    """AC: an unresolvable previous version is 'skipped', not silently ignored."""
    steps = _rollback().rollback_to(VersionString("unknown"))

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "Reinstall manually" in steps[0].detail
    assert "Cannot determine previous version" in steps[0].detail


def test_rollback_blank_previous_version_returns_skipped_message() -> None:
    """An empty version is the same unresolvable case as 'unknown'."""
    steps = _rollback().rollback_to(VersionString(""))

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "Reinstall manually" in steps[0].detail


def test_rollback_editable_install_returns_skipped_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """AC: an editable install names git as the recovery path, not pip."""

    (tmp_path / "pyproject.toml").write_text('name = "qwen-web-arwaky"\nversion = "6.5.0"\n', encoding="utf-8")
    (tmp_path / "modules").mkdir()
    monkeypatch.chdir(tmp_path)

    steps = _rollback(tmp_path, monkeypatch=monkeypatch).rollback_to(VersionString("6.4.0"))

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "git checkout" in steps[0].detail
    assert "6.4.0" in steps[0].detail


def test_rollback_refuses_when_release_cannot_be_pinned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An unpinnable release fails closed rather than installing a mutable tag."""
    monkeypatch.setattr(rollback_module, "resolve_editable_source_dir", lambda _package_name: None)
    monkeypatch.setattr(rollback_module, "resolve_github_pinned_url", lambda _version: None)

    rollback = _rollback(tmp_path, monkeypatch=monkeypatch)
    steps = rollback.rollback_to(VersionString("6.4.0"))

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "refusing to install unverified remote code" in steps[0].detail
