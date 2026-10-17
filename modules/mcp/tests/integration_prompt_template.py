"""Integration tests for built-in prompt template usage in the MCP surface."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.mcp.src.surface_mcp_tool_command import McpToolCommand
from modules.shared.src.common.taxonomy_core_vo import ResponseText
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptResponse


class TestMcpPromptTemplateIntegration:
    """Test MCP tool methods with role template input."""

    def test_mcp_file_only_with_role(self) -> None:
        prompt_aggregate = MagicMock()
        prompt_aggregate.execute.return_value = PromptResponse(
            response_text=ResponseText("Mock result")
        )

        cmd = McpToolCommand(
            prompt=prompt_aggregate,
            session=MagicMock(),
            setup=MagicMock(),
            workspace=MagicMock(),
            jobs=None,
        )

        res = cmd.process_prompt_file_only(input_file="frontend-engineer", async_run=False)
        assert "Mock result" in res
        prompt_aggregate.execute.assert_called_once()
        called_prompt = prompt_aggregate.execute.call_args.args[0]
        assert called_prompt.verb == "process_prompt_file_only"
        assert str(called_prompt.prompt_file).endswith("frontend-engineer.md")

    def test_mcp_attachment_with_role(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QWEN_WORKSPACE_ROOT", str(tmp_path))
        dummy_att = tmp_path / "code.py"
        dummy_att.write_text("print('hello')")

        prompt_aggregate = MagicMock()
        prompt_aggregate.execute.return_value = PromptResponse(
            response_text=ResponseText("Mock attachment result")
        )

        cmd = McpToolCommand(
            prompt=prompt_aggregate,
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
        prompt_aggregate.execute.assert_called_once()
        called_prompt = prompt_aggregate.execute.call_args.args[0]
        assert called_prompt.verb == "process_prompt_with_attachment"
        assert str(called_prompt.prompt_file).endswith("business-analyst.md")
