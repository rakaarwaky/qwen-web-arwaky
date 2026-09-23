"""FR-002 envelope contract tests for the MCP tool surface.

Every successful MCP payload must be parseable the same way regardless of which
code path produced it: an agent reading ``status`` must never hit a missing key.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.mcp.src.surface_mcp_tool_command import (
    STATUS_ACCEPTED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    McpToolCommand,
)
from modules.shared.src.taxonomy_core_error import RateLimitError
from modules.shared.src.taxonomy_core_vo import ErrorReason, JobRecord


def _job_record(**overrides) -> JobRecord:
    base = {
        "job_id": "file_20260922_000000_abc123",
        "created_at": "2026-09-22T00:00:00Z",
        "latest_event": "EVENT_DISPATCH_ACKNOWLEDGED",
        "completed": False,
        "input_file": "/ws/prompt.md",
        "output_file": "/ws/out.md",
    }
    base.update(overrides)
    return JobRecord(**base)


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


def _prompt(tmp_path: Path) -> Path:
    path = tmp_path / "prompt.md"
    path.write_text("# Prompt", encoding="utf-8")
    return path


def test_async_submission_carries_accepted_status(tools_and_mocks, tmp_path) -> None:
    """The default async path must expose the FR-002 status discriminator."""
    tools, _, jobs = tools_and_mocks
    jobs.submit_file_job.return_value = _job_record()

    payload = json.loads(tools.process_prompt_file_only(str(_prompt(tmp_path))))

    assert payload["success"] is True
    assert payload["status"] == STATUS_ACCEPTED
    assert payload["job_id"]


def test_sync_execution_carries_success_status(tools_and_mocks, tmp_path) -> None:
    """The synchronous path keeps returning the SUCCESS envelope."""
    tools, mocks, _ = tools_and_mocks
    mocks["file_only"].process_prompt_file_only.return_value = "answer text"

    payload = json.loads(tools.process_prompt_file_only(str(_prompt(tmp_path)), async_run=False))

    assert payload["status"] == STATUS_SUCCESS
    assert payload["result"] == "answer text"


def test_sync_and_async_envelopes_share_a_discriminator(tools_and_mocks, tmp_path) -> None:
    """A consumer reading `status` must never encounter a missing key."""
    tools, mocks, jobs = tools_and_mocks
    jobs.submit_file_job.return_value = _job_record()
    mocks["file_only"].process_prompt_file_only.return_value = "answer text"
    prompt = str(_prompt(tmp_path))

    async_payload = json.loads(tools.process_prompt_file_only(prompt))
    sync_payload = json.loads(tools.process_prompt_file_only(prompt, async_run=False))

    for payload in (async_payload, sync_payload):
        assert {"success", "status"} <= payload.keys()
        assert ("result" in payload) or ("job_id" in payload)


def test_attachment_async_submission_carries_accepted_status(tools_and_mocks, tmp_path) -> None:
    """Attachment submissions follow the same envelope as file-only ones."""
    tools, _, jobs = tools_and_mocks
    jobs.submit_attachment_job.return_value = _job_record(attachment_file="/ws/doc.pdf")
    attachment = tmp_path / "doc.pdf"
    attachment.write_text("data", encoding="utf-8")

    payload = json.loads(tools.process_prompt_with_attachment(str(_prompt(tmp_path)), str(attachment)))

    assert payload["status"] == STATUS_ACCEPTED


@pytest.mark.parametrize(
    ("completed", "error", "expected"),
    [
        (False, None, STATUS_RUNNING),
        (True, None, STATUS_COMPLETED),
        (True, "boom", STATUS_FAILED),
    ],
)
def test_get_job_status_reports_lifecycle_status(tools_and_mocks, completed, error, expected) -> None:
    """Polling a job must describe its lifecycle through the same field."""
    tools, _, jobs = tools_and_mocks
    jobs.get_job_status.return_value = _job_record(completed=completed, error=error)

    payload = json.loads(tools.get_job_status("file_20260922_000000_abc123"))

    assert payload["status"] == expected


def test_list_jobs_annotates_every_entry(tools_and_mocks) -> None:
    """Listed jobs each carry a status so the UI need not infer one."""
    tools, _, jobs = tools_and_mocks
    jobs.list_jobs.return_value = [
        _job_record(job_id="a", completed=True),
        _job_record(job_id="b", completed=True, error="boom"),
    ]

    payload = json.loads(tools.list_jobs(10))

    assert payload["status"] == STATUS_SUCCESS
    assert [item["status"] for item in payload["jobs"]] == [STATUS_COMPLETED, STATUS_FAILED]


def test_rate_limited_submission_returns_retry_hint(tools_and_mocks, tmp_path) -> None:
    """Throttling must surface as a retryable error, not a hung tool call."""
    tools, _, jobs = tools_and_mocks
    jobs.submit_file_job.side_effect = RateLimitError(ErrorReason("rate limit reached"), retry_after_sec=12.34)

    payload = json.loads(tools.process_prompt_file_only(str(_prompt(tmp_path))))

    assert payload["success"] is False
    assert payload["error"]["code"] == "RATE_LIMITED"
    assert payload["error"]["retryable"] is True
    assert payload["error"]["retry_after_sec"] == pytest.approx(12.3)


def test_direct_prompt_forwards_output_file(tools_and_mocks, tmp_path) -> None:
    """CLI parity: `output_file` must reach the aggregate and the envelope."""
    tools, mocks, _ = tools_and_mocks
    mocks["direct"].process_direct_prompt.return_value = "answer"
    destination = tmp_path / "result.md"

    payload = json.loads(tools.process_direct_prompt("hello", output_file=str(destination)))

    assert mocks["direct"].process_direct_prompt.call_args.kwargs["output_file"] == destination.resolve()
    assert payload["output_path"] == str(destination.resolve())
    assert payload["status"] == STATUS_SUCCESS


def test_direct_prompt_tool_schema_declares_output_file() -> None:
    """The declared MCP schema must advertise the parameter it now accepts."""
    from modules.root_mcp_main_entry import TOOLS

    tool = next(t for t in TOOLS if t.name == "process_direct_prompt")

    assert "output_file" in tool.input_schema["properties"]
