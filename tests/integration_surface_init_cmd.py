"""Unit tests for qwa init command and workspace initialization logic."""

import tempfile
import unittest
from pathlib import Path

from modules.core.src.root_core_container import SharedContainer
from modules.shared.src import DEFAULT_LOG, DEFAULT_OUTPUT


class TestQwaInit(unittest.TestCase):
    """Test suite for qwa init functionality."""

    def test_run_init_creates_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir)

            # Execute init via core aggregate directly
            container = SharedContainer()
            container.workspace.init_workspace(target_path)

            # 1. Verify .agents/skills/qwen-web/SKILL.md
            skill_md = target_path / ".agents" / "skills" / "qwen-web" / "SKILL.md"
            self.assertTrue(skill_md.exists())
            content = skill_md.read_text(encoding="utf-8")
            self.assertIn("name: qwen-web", content)

            # 2. Verify .qwen-web symlinks
            dot_qwen = target_path / ".qwen-web"
            self.assertTrue(dot_qwen.exists())

            log_link = dot_qwen / "log"
            output_link = dot_qwen / "output"
            session_link = dot_qwen / "qwen_session"

            self.assertTrue(log_link.is_symlink())
            self.assertTrue(output_link.is_symlink())
            self.assertTrue(session_link.is_symlink())

            self.assertEqual(log_link.resolve(), DEFAULT_LOG.resolve())
            self.assertEqual(output_link.resolve(), DEFAULT_OUTPUT.resolve())

            # 3. Verify .gitignore
            gitignore = target_path / ".gitignore"
            self.assertTrue(gitignore.exists())
            gi_content = gitignore.read_text(encoding="utf-8")
            self.assertIn(".qwen-web/", gi_content)

    def test_run_init_idempotent_and_existing_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir)
            gitignore = target_path / ".gitignore"
            gitignore.write_text("existing_file.txt\n", encoding="utf-8")

            # First run
            container = SharedContainer()
            container.workspace.init_workspace(target_path)
            gi_content = gitignore.read_text(encoding="utf-8")
            self.assertIn("existing_file.txt", gi_content)
            self.assertIn(".qwen-web/", gi_content)

            # Second run (idempotency check)
            container.workspace.init_workspace(target_path)
            gi_content_2 = gitignore.read_text(encoding="utf-8")
            self.assertEqual(gi_content_2.count(".qwen-web/"), 1)


if __name__ == "__main__":
    unittest.main()
