"""Unit tests for the jobs CLI surface (surface_cli_jobs_command)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_jobs_command import handle as handle_jobs_command
from modules.shared.src.taxonomy_core_vo import JobRecord


def _record(
    job_id: str = "job-1",
    *,
    completed: bool = False,
    error: str | None = None,
    input_file: str | None = "task.md",
) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        created_at="2026-10-10T00:00:00",
        latest_event="DISPATCH_ACKNOWLEDGED",
        completed=completed,
        input_file=input_file,
        error=error,
    )


def _submit_args(prompt_path: str = "task.md", json_output: bool = False) -> MagicMock:
    args = MagicMock()
    args.job_command = "submit"
    args.prompt_path = prompt_path
    args.attachment_path = None
    args.output_path = None
    args.headless = True
    args.json = json_output
    return args


class TestJobsSubmit:
    def test_submit_returns_job_id_and_poll_hints(self, tmp_path, capsys) -> None:
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        prompt_file = tmp_path / "task.md"
        prompt_file.write_text("test prompt")
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=_record(), error=None)
        rc = handle_jobs_command(_submit_args(str(prompt_file)), jobs)
        assert rc == 0
        out = capsys.readouterr().out
        assert "job-1" in out
        assert "jobs status" in out

    def test_submit_with_attachment_uses_the_attachment_verb(self, tmp_path) -> None:
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        prompt_file = tmp_path / "task.md"
        prompt_file.write_text("test prompt")
        attachment_file = tmp_path / "att.pdf"
        attachment_file.write_text("attachment")
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=_record(), error=None)
        args = _submit_args(str(prompt_file))
        args.attachment_path = str(attachment_file)
        rc = handle_jobs_command(args, jobs)
        assert rc == 0
        verb = jobs.execute.call_args[0][0].verb
        assert verb == "submit_attachment_job"

    def test_submit_file_only_uses_the_file_verb(self, tmp_path) -> None:
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        prompt_file = tmp_path / "task.md"
        prompt_file.write_text("test prompt")
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=_record(), error=None)
        rc = handle_jobs_command(_submit_args(str(prompt_file)), jobs)
        assert rc == 0
        assert jobs.execute.call_args[0][0].verb == "submit_file_job"

    def test_submit_json_envelope(self, tmp_path, capsys) -> None:
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        prompt_file = tmp_path / "task.md"
        prompt_file.write_text("test prompt")
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=_record(), error=None)
        rc = handle_jobs_command(_submit_args(str(prompt_file), json_output=True), jobs)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is True
        assert payload["job_id"] == "job-1"

    def test_submit_role_template_resolves_path(self, tmp_path, capsys) -> None:
        """A role-template string (e.g. 'code-review') is materialised before submission."""
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        materialised = Path("/tmp/qwa-templates/code-review.md")
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=_record(input_file="code-review.md"), error=None)
        args = _submit_args(prompt_path="code-review")
        with (
            patch(
                "modules.cli.src.surface_cli_jobs_command.materialize_role_template",
                return_value=materialised,
            ),
            patch(
                "modules.cli.src.surface_cli_jobs_command.is_prompt_role",
                return_value=True,
            ),
        ):
            rc = handle_jobs_command(args, jobs)
        assert rc == 0
        # The resolved materialised path should reach JobRequest.prompt_file.
        request = jobs.execute.call_args[0][0]
        assert request.prompt_file == str(materialised)

    def test_submit_regular_file_path_resolves_path(self, tmp_path, capsys) -> None:
        """A regular file path is resolved (not materialised) before submission."""
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        target = tmp_path / "task.md"
        target.write_text("test prompt")
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=_record(input_file="task.md"), error=None)
        args = _submit_args(prompt_path=str(target))
        rc = handle_jobs_command(args, jobs)
        assert rc == 0
        request = jobs.execute.call_args[0][0]
        assert request.prompt_file == str(target.resolve())

    def test_submit_failure_returns_nonzero(self, tmp_path, capsys) -> None:
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        prompt_file = tmp_path / "task.md"
        prompt_file.write_text("test prompt")
        jobs = MagicMock()
        jobs.execute.side_effect = RuntimeError("pool down")
        rc = handle_jobs_command(_submit_args(str(prompt_file)), jobs)
        assert rc == 1
        assert "Job submission failed" in capsys.readouterr().err

    def test_submit_outside_workspace_rejected(self, tmp_path, capsys) -> None:
        """A prompt path outside the workspace is rejected."""
        os.environ["QWEN_WORKSPACE_ROOT"] = str(tmp_path)
        outside = tmp_path.parent / "outside.md"
        outside.write_text("secret")
        jobs = MagicMock()
        rc = handle_jobs_command(_submit_args(prompt_path=str(outside)), jobs)
        assert rc == 1
        err = capsys.readouterr().err
        assert "PATH_OUTSIDE_WORKSPACE" in err or "outside the workspace" in err


class TestJobsStatus:
    def test_status_found_prints_fields(self, capsys) -> None:
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=_record(completed=True), error=None)
        args = MagicMock()
        args.job_command = "status"
        args.job_id = "job-1"
        args.json = False
        rc = handle_jobs_command(args, jobs)
        assert rc == 0
        assert "job-1" in capsys.readouterr().out

    def test_status_unknown_job_returns_nonzero(self, capsys) -> None:
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(record=None, error=None)
        args = MagicMock()
        args.job_command = "status"
        args.job_id = "missing"
        args.json = False
        rc = handle_jobs_command(args, jobs)
        assert rc == 1
        assert "Job not found" in capsys.readouterr().out


class TestJobsList:
    def test_list_empty_prints_hint(self, capsys) -> None:
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(records=[], error=None)
        args = MagicMock()
        args.job_command = "list"
        args.limit = 10
        args.json = False
        rc = handle_jobs_command(args, jobs)
        assert rc == 0
        assert "No jobs found" in capsys.readouterr().out

    def test_list_formats_table_rows(self, capsys) -> None:
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(records=[_record()], error=None)
        args = MagicMock()
        args.job_command = "list"
        args.limit = 10
        args.json = False
        rc = handle_jobs_command(args, jobs)
        assert rc == 0
        out = capsys.readouterr().out
        assert "job-1" in out
        assert "RUNNING" in out

    def test_list_json_envelope(self, capsys) -> None:
        jobs = MagicMock()
        jobs.execute.return_value = MagicMock(records=[_record()], error=None)
        args = MagicMock()
        args.job_command = "list"
        args.limit = 10
        args.json = True
        rc = handle_jobs_command(args, jobs)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["total"] == 1
        assert payload["jobs"][0]["job_id"] == "job-1"


class TestJobsCleanup:
    def test_cleanup_reports_removed_count(self, capsys) -> None:
        storage = MagicMock()
        storage.cleanup_stale_jobs.return_value = 3
        args = MagicMock()
        args.job_command = "cleanup"
        args.json = False
        rc = handle_jobs_command(args, MagicMock(), storage)
        assert rc == 0
        assert "3" in capsys.readouterr().out

    def test_cleanup_failure_returns_nonzero(self, capsys) -> None:
        storage = MagicMock()
        storage.cleanup_stale_jobs.side_effect = OSError("disk full")
        args = MagicMock()
        args.job_command = "cleanup"
        args.json = False
        rc = handle_jobs_command(args, MagicMock(), storage)
        assert rc == 1
        assert "Cleanup failed" in capsys.readouterr().err

    def test_cleanup_without_storage_is_refused(self, capsys) -> None:
        args = MagicMock()
        args.job_command = "cleanup"
        args.json = False
        rc = handle_jobs_command(args, MagicMock(), None)
        assert rc == 1
        assert "Job storage not available" in capsys.readouterr().err


class TestJobsDispatch:
    def test_unknown_verb_returns_usage(self, capsys) -> None:
        args = MagicMock()
        args.job_command = "bogus"
        rc = handle_jobs_command(args, MagicMock())
        assert rc == 1
        assert "--help" in capsys.readouterr().out
