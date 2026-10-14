"""Integration tests for built-in prompt template usage in the MCP surface."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.mcp.src.surface_mcp_tool_command import McpToolCommand


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

        res = cmd.process_prompt_file_only(input_file="frontend-engineer", async_run=False)
        assert "Mock result" in res
        mock_file_only.process_prompt_file_only.assert_called_once()
        called_prompt = mock_file_only.process_prompt_file_only.call_args[0][0]
        assert str(called_prompt).endswith("frontend-engineer.md")

    def test_mcp_attachment_with_role(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QWEN_WORKSPACE_ROOT", str(tmp_path))
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
            prompt_file="business-analyst",
            attachment_file=str(dummy_att),
            async_run=False,
        )
        assert "Mock attachment result" in res
        mock_attachment.process_prompt_with_attachment.assert_called_once()
        called_prompt = mock_attachment.process_prompt_with_attachment.call_args[0][0]
        assert str(called_prompt).endswith("business-analyst.md")
