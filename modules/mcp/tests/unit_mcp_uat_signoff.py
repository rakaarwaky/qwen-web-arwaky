"""MCP UAT sign-off scenarios for the AI agent consumer persona (issue #286).

Each test corresponds to a row of the "UAT Sign-off Criteria" table in
`modules/mcp/FRD.md`. Aggregates are mocked so the scenarios lock the tool
contract — the JSON an AI agent actually receives — without a live Qwen
session or a browser. The parsed payload is the recorded evidence: every
assertion names the exact keys the consumer branches on.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.mcp.src.surface_mcp_tool_command import (
    STATUS_ACCEPTED,
    STATUS_COMPLETED,
    STATUS_RUNNING,
    McpToolCommand,
)
from modules.shared.src.taxonomy_core_vo import JobRecord

pytestmark = pytest.mark.uat


@pytest.fixture
def tools_and_mocks(tmp_path, monkeypatch):
    """Build an McpToolCommand whose aggregates are all mocks."""
    monkeypatch.setenv("QWEN_WORKSPACE_ROOT", str(tmp_path))
    mocks = {name: MagicMock() for name in ("direct", "file_only", "attachment", "session", "setup", "workspace")}
    jobs = MagicMock()
    tools = McpToolCommand(
        direct=mocks["direct"],
        file_only=mocks["file_only"],
        attachment=mocks["attachment"],
        session=mocks["session"],
        setup=mocks["setup"],
        workspace=mocks["workspace"],
        jobs=jobs,
    )
    return tools, mocks, jobs


def _job_record(**overrides) -> JobRecord:
    base: dict = {
        "job_id": "file_20260922_000000_abc123",
        "created_at": "2026-09-22T00:00:00Z",
        "latest_event": "EVENT_DISPATCH_ACKNOWLEDGED",
        "completed": False,
        "input_file": "/ws/prompt.md",
        "output_file": "/ws/out.md",
    }
    base.update(overrides)
    return JobRecord(**base)


def _prompt(tmp_path: Path) -> Path:
    path = tmp_path / "prompt.md"
    path.write_text("# Prompt", encoding="utf-8")
    return path


def test_uat_mcp_004_delete_session_without_confirm_is_refused(tools_and_mocks) -> None:
    """UAT-MCP-004: delete_session(confirm=False) is rejected, session intact."""
    tools, mocks, _ = tools_and_mocks

    payload = json.loads(tools.delete_session(confirm=False))

    assert payload["success"] is False
    assert payload["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert payload["error"]["hint"]
    mocks["session"].delete_session.assert_not_called()


def test_uat_mcp_005_delete_session_with_confirm_succeeds(tools_and_mocks) -> None:
    """UAT-MCP-005: delete_session(confirm=True) delegates and reports success."""
    tools, mocks, _ = tools_and_mocks

    payload = json.loads(tools.delete_session(confirm=True))

    assert payload["success"] is True
    assert payload["next_action"] == "setup_session"
    mocks["session"].delete_session.assert_called_once()


def test_uat_mcp_006_async_job_full_lifecycle(tools_and_mocks, tmp_path) -> None:
    """UAT-MCP-006: submit → poll (ACCEPTED, RUNNING) → COMPLETED with output file."""
    tools, _, jobs = tools_and_mocks
    jobs.submit_file_job.return_value = _job_record()
    output_file = tmp_path / "out.md"

    accepted = json.loads(tools.process_prompt_file_only(str(_prompt(tmp_path))))
    assert accepted["status"] == STATUS_ACCEPTED
    job_id = accepted["job_id"]

    jobs.get_job_status.side_effect = [
        _job_record(job_id=job_id),
        _job_record(
            job_id=job_id,
            completed=True,
            latest_event="EVENT_OUTPUT_COPIED",
            output_file=str(output_file),
        ),
    ]
    first = json.loads(tools.get_job_status(job_id))
    assert first["status"] == STATUS_RUNNING

    second = json.loads(tools.get_job_status(job_id))
    assert second["status"] == STATUS_COMPLETED
    assert second["success"] is True
    assert second["output_file"] == str(output_file)


def test_uat_mcp_007_empty_prompt_is_rejected(tools_and_mocks) -> None:
    """UAT-MCP-007: process_direct_prompt("") reports VALIDATION_ERROR on field=prompt."""
    tools, mocks, _ = tools_and_mocks

    payload = json.loads(tools.process_direct_prompt("   "))

    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["field"] == "prompt"
    mocks["direct"].process_direct_prompt.assert_not_called()


def test_uat_mcp_008_setup_session_error_carries_actionable_hint(tools_and_mocks) -> None:
    """UAT-MCP-008: a failed setup_session surfaces a hint, not a bare traceback."""
    tools, mocks, _ = tools_and_mocks
    mocks["setup"].setup_session.side_effect = RuntimeError("Browser launch requires a display")

    payload = json.loads(tools.setup_session())

    assert payload["success"] is False
    assert payload["error"]["code"] == "SETUP_SESSION_FAILED"
    assert payload["error"]["hint"]
    assert payload["error"]["retryable"] is False


def test_uat_mcp_009_unwritable_init_workspace_target_is_reported(tools_and_mocks, tmp_path) -> None:
    """UAT-MCP-009: init_workspace on an unwritable target reports the error path."""
    tools, mocks, _ = tools_and_mocks
    mocks["workspace"].init_workspace.side_effect = PermissionError(f"{tmp_path}: permission denied")

    payload = json.loads(tools.init_workspace(str(tmp_path)))

    assert payload["success"] is False
    assert payload["error"]["code"]
    assert payload["error"]["hint"]
