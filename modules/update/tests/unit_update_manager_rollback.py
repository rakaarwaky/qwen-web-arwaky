"""Issue #279: rollback-status edge cases locked offline.

Covers the business rules the BA review surfaced — unknown previous version,
editable installs, and partial rollback reporting — without touching the
network or running a real pip.
"""

from __future__ import annotations

import pytest

from modules.update.src.capabilities_update_manager import UpdateManager


def test_rollback_unknown_previous_version_returns_skipped_message() -> None:
    """AC: an unresolvable previous version is 'skipped', not silently ignored."""
    steps = UpdateManager().rollback_to("unknown")

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "Reinstall manually" in steps[0].detail
    assert "Cannot determine previous version" in steps[0].detail


def test_rollback_blank_previous_version_returns_skipped_message() -> None:
    """An empty version is the same unresolvable case as 'unknown'."""
    steps = UpdateManager().rollback_to("")

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "Reinstall manually" in steps[0].detail


def test_rollback_editable_install_returns_skipped_message(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """AC: an editable install names git as the recovery path, not pip."""
    (tmp_path / "pyproject.toml").write_text('name = "qwen-web-arwaky"\nversion = "6.5.0"\n', encoding="utf-8")
    (tmp_path / "modules").mkdir()
    monkeypatch.chdir(tmp_path)

    steps = UpdateManager().rollback_to("6.4.0")

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "git checkout" in steps[0].detail
    assert "6.4.0" in steps[0].detail


def test_rollback_refuses_when_release_cannot_be_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unpinnable release fails closed rather than installing a mutable tag."""
    monkeypatch.setattr(UpdateManager, "_editable_source_dir", lambda self: None)
    monkeypatch.setattr(UpdateManager, "_github_pinned_url", lambda self, v: None)

    steps = UpdateManager().rollback_to("6.4.0")

    assert len(steps) == 1
    assert steps[0].executed is False
    assert "refusing to install unverified remote code" in steps[0].detail
