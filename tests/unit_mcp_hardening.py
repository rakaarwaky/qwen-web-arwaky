"""Regression tests for MCP registry and prompt-file safety hardening."""

from __future__ import annotations

import json

from modules.mcp.src.surface_mcp_tool_command import _validate_attachment_path, _validate_prompt_path
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


def _workspace(tmp_path, monkeypatch):
    """Create an isolated workspace root and point MCP validation at it."""
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("QWEN_WORKSPACE_ROOT", str(root))
    return root


def test_prompt_path_rejects_symlink_escaping_workspace(tmp_path, monkeypatch) -> None:
    """A symlink inside the workspace must not expose files outside it."""
    root = _workspace(tmp_path, monkeypatch)
    outside = tmp_path / "secret.md"
    outside.write_text("sensitive", encoding="utf-8")
    link = root / "innocent.md"
    link.symlink_to(outside)

    path, error = _validate_prompt_path(str(link))

    assert path is None
    assert error is not None
    assert json.loads(error)["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_prompt_path_rejects_dotdot_traversal(tmp_path, monkeypatch) -> None:
    """Relative traversal must not climb out of the workspace root."""
    root = _workspace(tmp_path, monkeypatch)
    outside = tmp_path / "prompt.md"
    outside.write_text("prompt", encoding="utf-8")

    path, error = _validate_prompt_path(str(root / ".." / "prompt.md"))

    assert path is None
    assert error is not None
    assert json.loads(error)["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_prompt_path_accepts_file_inside_workspace(tmp_path, monkeypatch) -> None:
    """The happy path must keep working so the guard is not vacuously strict."""
    root = _workspace(tmp_path, monkeypatch)
    prompt = root / "task.md"
    prompt.write_text("# Task", encoding="utf-8")

    path, error = _validate_prompt_path(str(prompt))

    assert error is None
    assert path == prompt.resolve()


def test_attachment_path_rejects_symlink_escaping_workspace(tmp_path, monkeypatch) -> None:
    """Attachment validation must enforce the same boundary as prompts."""
    root = _workspace(tmp_path, monkeypatch)
    outside = tmp_path / "secret.pdf"
    outside.write_text("sensitive", encoding="utf-8")
    link = root / "doc.pdf"
    link.symlink_to(outside)

    path, error = _validate_attachment_path(str(link))

    assert path is None
    assert error is not None
    assert json.loads(error)["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_attachment_path_accepts_directory_inside_workspace(tmp_path, monkeypatch) -> None:
    """Folder attachments inside the workspace remain valid."""
    root = _workspace(tmp_path, monkeypatch)
    folder = root / "docs"
    folder.mkdir()

    path, error = _validate_attachment_path(str(folder))

    assert error is None
    assert path == folder.resolve()
