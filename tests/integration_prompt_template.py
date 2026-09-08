"""Integration tests for built-in prompt template usage in CLI and MCP surfaces."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from modules.mcp.src.surface_mcp_tool_command import McpToolCommand
from modules.root_cli_main_entry import _build_config, _parse_args


class TestCliPromptTemplateIntegration:
    """Test CLI argument parsing and config construction for role templates."""

    def test_prompt_only_with_role(self) -> None:
        args = _parse_args(["prompt-only", "-i", "architect", "--headless"])
        cfg = _build_config(args)

        assert cfg.mode == "single"
        assert cfg.prompt_path is not None
        assert cfg.prompt_path.exists()
        assert cfg.prompt_path.name == "architect.md"
        assert cfg.output_path.name == "architect_output.md"
        assert cfg.headless is True

    def test_prompt_with_attachment_and_role(self, tmp_path: Path) -> None:
        dummy_att = tmp_path / "dummy.txt"
        dummy_att.write_text("hello world")

        args = _parse_args(["prompt-with-attachment", "-i", "backend", "-a", str(dummy_att)])
        cfg = _build_config(args)

        assert cfg.mode == "single"
        assert cfg.prompt_path is not None
        assert cfg.prompt_path.exists()
        assert cfg.prompt_path.name == "backend.md"
        assert cfg.file_path == dummy_att.resolve()
        assert cfg.output_path.name == "backend_output.md"


class TestMcpPromptTemplateIntegration:
    """Test MCP tool methods with role template input."""

    def test_mcp_file_only_with_role(self) -> None:
        mock_file_only = MagicMock()
        mock_file_only.process_prompt_file_only.return_value = "Mock result"

        cmd = McpToolCommand(
            direct=MagicMock(),
            attachment=MagicMock(),
            file_only=mock_file_only,
            session=MagicMock(),
            setup=MagicMock(),
            workspace=MagicMock(),
            jobs=None,
        )

        res = cmd.process_prompt_file_only(input_file="frontend", async_run=False)
        assert "Mock result" in res
        mock_file_only.process_prompt_file_only.assert_called_once()
        called_prompt = mock_file_only.process_prompt_file_only.call_args[0][0]
        assert str(called_prompt).endswith("frontend.md")

    def test_mcp_attachment_with_role(self, tmp_path: Path) -> None:
        dummy_att = tmp_path / "code.py"
        dummy_att.write_text("print('hello')")

        mock_attachment = MagicMock()
        mock_attachment.process_prompt_with_attachment.return_value = "Mock attachment result"

        cmd = McpToolCommand(
            direct=MagicMock(),
            attachment=mock_attachment,
            file_only=MagicMock(),
            session=MagicMock(),
            setup=MagicMock(),
            workspace=MagicMock(),
            jobs=None,
        )

        res = cmd.process_prompt_with_attachment(
            prompt_file="analyst",
            attachment_file=str(dummy_att),
            async_run=False,
        )
        assert "Mock attachment result" in res
        mock_attachment.process_prompt_with_attachment.assert_called_once()
        called_prompt = mock_attachment.process_prompt_with_attachment.call_args[0][0]
        assert str(called_prompt).endswith("analyst.md")


class TestTuiPromptTemplateIntegration:
    """Test TUI role template resolution."""

    def test_tui_action_run_action_with_role(self) -> None:
        from modules.cli.src.surface_cli_tui_app import QwenTuiApp

        app = QwenTuiApp(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())

        mock_input_prompt = MagicMock(value="architect")
        mock_input_file = MagicMock(value="")
        mock_input_output = MagicMock(value="")
        mock_switch = MagicMock(value=True)

        def fake_query_one(selector: str, *args: object, **kwargs: object) -> MagicMock:
            if selector.startswith("#input-prompt"):
                return mock_input_prompt
            if selector.startswith("#input-file"):
                return mock_input_file
            if selector.startswith("#input-output"):
                return mock_input_output
            if selector.startswith("#switch-headless"):
                return mock_switch
            return MagicMock()

        app.query_one = fake_query_one  # type: ignore[assignment]
        app._execute_slot_worker = MagicMock()  # type: ignore[assignment]
        app._run_slot(1)

        app._execute_slot_worker.assert_called_once()
        cfg = app._execute_slot_worker.call_args[0][1]
        assert cfg.prompt_path is not None
        assert cfg.prompt_path.name == "architect.md"
        assert cfg.prompt_path.exists()
