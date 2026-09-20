"""Regression tests for MCP registry and prompt-file safety hardening."""

from __future__ import annotations

import json

from modules.mcp.src.surface_mcp_tool_command import _validate_prompt_path
from modules.root_mcp_main_entry import TOOL_HANDLERS, TOOLS


def test_registered_tools_have_exactly_one_async_handler() -> None:
    """The live registry and handler map must remain one-to-one."""
    assert {tool.name for tool in TOOLS} == set(TOOL_HANDLERS)


def test_prompt_path_rejects_files_outside_workspace(tmp_path, monkeypatch) -> None:
    """MCP must not read prompt files outside its configured workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "secret.md"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.setenv("QWEN_WORKSPACE_ROOT", str(workspace))

    path, error = _validate_prompt_path(str(outside))

    assert path is None
    assert error is not None
    assert json.loads(error)["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"
