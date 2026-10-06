"""Integration tests for the session workspace against a real filesystem.

These create real directories and symlinks in a temporary tree, so the
provisioning steps are exercised against the filesystem rather than a stub.
"""

from __future__ import annotations

from pathlib import Path

from modules.session.src.capabilities_workspace_provisioner import WorkspaceProvisioner


def test_integration_init_provisions_the_skill_document(tmp_path: Path) -> None:
    WorkspaceProvisioner().init_workspace(tmp_path)

    assert (tmp_path / ".agents" / "skills" / "qwen-web" / "SKILL.md").is_file()


def test_integration_init_provisions_the_workspace_directory(tmp_path: Path) -> None:
    WorkspaceProvisioner().init_workspace(tmp_path)

    assert (tmp_path / ".qwen-web").is_dir()


def test_integration_init_records_the_workspace_in_gitignore(tmp_path: Path) -> None:
    """The workspace holds session symlinks, so it must be ignored rather
    than committed alongside the operator's own work."""
    WorkspaceProvisioner().init_workspace(tmp_path)

    assert ".qwen-web/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_integration_reinitializing_preserves_an_existing_workspace(tmp_path: Path) -> None:
    """Re-initialization must not discard a workspace, because that would
    sign the operator out of every saved session at once."""
    provisioner = WorkspaceProvisioner()
    provisioner.init_workspace(tmp_path)
    marker = tmp_path / ".qwen-web" / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")

    provisioner.init_workspace(tmp_path)

    assert marker.read_text(encoding="utf-8") == "keep me"
