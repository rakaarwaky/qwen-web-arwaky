"""Integration tests for built-in prompt template usage in the CLI surface."""

from __future__ import annotations

from pathlib import Path

from modules.root_cli_main_entry import _build_config, _parse_args


class TestCliPromptTemplateIntegration:
    """Test CLI argument parsing and config construction for role templates."""

    def test_prompt_only_with_role(self) -> None:
        args = _parse_args(["prompt", "file", "-i", "software-architect", "--headless"])
        cfg = _build_config(args)

        assert cfg.mode == "single"
        assert cfg.prompt_path is not None
        assert cfg.prompt_path.exists()
        assert cfg.prompt_path.name == "software-architect.md"
        assert cfg.output_path.name == "software-architect_output.md"
        assert cfg.headless is True

    def test_prompt_with_attachment_and_role(self, tmp_path: Path) -> None:
        dummy_att = tmp_path / "dummy.txt"
        dummy_att.write_text("hello world")

        args = _parse_args(["prompt", "attach", "-i", "backend-engineer", "-a", str(dummy_att)])
        cfg = _build_config(args)

        assert cfg.mode == "single"
        assert cfg.prompt_path is not None
        assert cfg.prompt_path.exists()
        assert cfg.prompt_path.name == "backend-engineer.md"
        assert cfg.file_path == dummy_att.resolve()
        assert cfg.output_path.name == "backend-engineer_output.md"
