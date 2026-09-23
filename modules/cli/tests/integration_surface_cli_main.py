"""Tests for main.py — workspace initialization (run_init)."""

from __future__ import annotations

from unittest.mock import patch

from modules.core.src.root_core_container import SharedContainer


class TestRunInit:
    def test_creates_skill_md(self, tmp_path):
        skill_dir = tmp_path / ".agents" / "skills" / "qwen-web"
        assert not skill_dir.exists()
        SharedContainer().workspace.init_workspace(tmp_path)
        assert (skill_dir / "SKILL.md").exists()
        assert "Qwen Web Automation" in (skill_dir / "SKILL.md").read_text()

    def test_creates_gitignore(self, tmp_path):
        SharedContainer().workspace.init_workspace(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".qwen-web/" in gitignore.read_text()

    def test_appends_to_existing_gitignore(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")
        SharedContainer().workspace.init_workspace(tmp_path)
        content = gitignore.read_text()
        assert ".qwen-web/" in content
        assert "*.pyc" in content

    def test_creates_symlinks(self, tmp_path):
        xdg_input = tmp_path / "xdg" / "input"
        xdg_output = tmp_path / "xdg" / "output"
        xdg_log = tmp_path / "xdg" / "log"
        for d in (xdg_input, xdg_output, xdg_log):
            d.mkdir(parents=True, exist_ok=True)
        with (
            patch("modules.core.src.capabilities_workspace_provisioner.DEFAULT_OUTPUT", xdg_output),
            patch("modules.core.src.capabilities_workspace_provisioner.DEFAULT_LOG", xdg_log),
        ):
            SharedContainer().workspace.init_workspace(tmp_path)
            dot_qwen = tmp_path / ".qwen-web"
            assert dot_qwen.exists()
            assert (dot_qwen / "output").exists()
            assert (dot_qwen / "log").exists()
