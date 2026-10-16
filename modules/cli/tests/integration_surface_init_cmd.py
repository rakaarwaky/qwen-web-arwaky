"""Unit tests for qwa init command and workspace initialization logic."""

import tempfile
import unittest
from pathlib import Path

from modules.root_core_container import SharedContainer
from modules.shared.src import DEFAULT_JOBS_DIR, DEFAULT_LOG, DEFAULT_OUTPUT, DEFAULT_SESSION, SWARM_OUTPUT_ROOT


class TestQwaInit(unittest.TestCase):
    """Test suite for qwa init functionality."""

    def test_run_init_creates_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir)

            # Execute init via core aggregate directly
            container = SharedContainer()
            container.workspace.init_workspace(target_path)

            # 1. Verify .agents/skills/qwen-web-arwaky/SKILL.md
            skill_md = target_path / ".agents" / "skills" / "qwen-web-arwaky" / "SKILL.md"
            self.assertTrue(skill_md.exists())
            content = skill_md.read_text(encoding="utf-8")
            self.assertIn("name: qwen-web-arwaky", content)

            # 2. Verify all five .qwen-web-arwaky symlinks (issue #319)
            dot_qwen = target_path / ".qwen-web-arwaky"
            self.assertTrue(dot_qwen.exists())

            link_targets = {
                "jobs": DEFAULT_JOBS_DIR,
                "log": DEFAULT_LOG,
                "output": DEFAULT_OUTPUT,
                "qwen_session": DEFAULT_SESSION,
                "swarm": SWARM_OUTPUT_ROOT,
            }
            for name, target in link_targets.items():
                link = dot_qwen / name
                self.assertTrue(link.is_symlink() or link.exists(), f".qwen-web-arwaky/{name} missing")
                self.assertEqual(link.resolve(), target.resolve(), f".qwen-web-arwaky/{name} target mismatch")

            # 3. Verify the nested .qwen-web-arwaky/.gitignore
            gitignore = dot_qwen / ".gitignore"
            self.assertTrue(gitignore.is_file())
            gi_content = gitignore.read_text(encoding="utf-8")
            self.assertIn("*", gi_content)
            self.assertIn("!.gitignore", gi_content)
            self.assertFalse((target_path / ".gitignore").exists())

    def test_run_init_idempotent_and_existing_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir)
            gitignore = target_path / ".gitignore"
            gitignore.write_text("existing_file.txt\n", encoding="utf-8")

            # First run: the nested .gitignore is created; the operator's
            # existing root .gitignore entries survive, but any legacy
            # .qwen-web-arwaky/ / .qwen-web/ entries init once appended
            # are cleaned up.
            container = SharedContainer()
            container.workspace.init_workspace(target_path)
            gi_content = gitignore.read_text(encoding="utf-8")
            self.assertIn("existing_file.txt", gi_content)
            self.assertNotIn(".qwen-web-arwaky/", gi_content)
            self.assertNotIn(".qwen-web/", gi_content)

            # Second run (idempotency check): the nested file is rewritten
            # with the canonical content and the root file stays clean.
            container.workspace.init_workspace(target_path)
            gi_content_2 = gitignore.read_text(encoding="utf-8")
            self.assertNotIn(".qwen-web-arwaky/", gi_content_2)
            self.assertNotIn(".qwen-web/", gi_content_2)
            nested = (target_path / ".qwen-web-arwaky" / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(nested.count("!.gitignore"), 1)


if __name__ == "__main__":
    unittest.main()
