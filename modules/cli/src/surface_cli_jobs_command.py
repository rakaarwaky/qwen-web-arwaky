"""CLI surface: jobs command — manage asynchronous background prompt jobs.

Smart surface: maps parsed args to the IJobManagerAggregate verbs
(submit_file_job, submit_attachment_job, get_job_status, list_jobs, cleanup_stale_jobs)
and formats the response as a human-readable table or JSON envelope.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.cli.src.surface_cli_json_hook import _fail_json, status_glyph
from modules.shared.src.common.taxonomy_core_error import JobQueueFullError
from modules.shared.src.common.taxonomy_core_vo import JobRecord
from modules.shared.src.common.utility_core_path_validation import (
    validate_attachment_path,
    validate_output_path,
    validate_prompt_path,
)
from modules.shared.src.common.utility_core_prompt_template import (
    is_prompt_role,
    materialize_role_template,
)
from modules.shared.src.jobs.contract_jobs_aggregate import IJobManagerAggregate
from modules.shared.src.jobs.taxonomy_jobs_vo import JobRequest


def _job_status(record: JobRecord) -> str:
    """Derive a human-readable status for a job record."""
    if not record.completed:
        return "RUNNING"
    return "FAILED" if record.error else "COMPLETED"


def _cmd_submit(args: argparse.Namespace, jobs: IJobManagerAggregate) -> int:
    """Submit a file or attachment prompt job to the background worker pool."""
    json_output = bool(getattr(args, "json", False))
    headless = bool(getattr(args, "headless", True))

    # Validate and resolve prompt path (handles role templates)
    prompt_raw = args.prompt_path
    prompt_path: Path | None
    if is_prompt_role(prompt_raw):
        prompt_path = materialize_role_template(prompt_raw)
    else:
        validated_path, error = validate_prompt_path(prompt_raw, field="prompt_file")
        if error is not None:
            return _fail_json(error["message"], "cli-400", json_output)
        prompt_path = validated_path

    # Validate attachment path if provided
    attachment_raw = getattr(args, "attachment_path", None)
    attachment_path = None
    if attachment_raw:
        validated_attachment, error = validate_attachment_path(attachment_raw, field="attachment_file")
        if error is not None:
            return _fail_json(error["message"], "cli-400", json_output)
        attachment_path = validated_attachment

    # Validate output path if provided
    output_raw = getattr(args, "output_path", None)
    output_path = None
    if output_raw:
        validated_output, error = validate_output_path(output_raw, field="output_file")
        if error is not None:
            return _fail_json(error["message"], "cli-400", json_output)
        output_path = validated_output

    # Build request
    try:
        if attachment_path:
            response = jobs.execute(
                JobRequest(
                    verb="submit_attachment_job",
                    prompt_file=str(prompt_path),
                    attachment_file=str(attachment_path),
                    output_file=str(output_path) if output_path else None,
                    headless=headless,
                )
            )
        else:
            response = jobs.execute(
                JobRequest(
                    verb="submit_file_job",
                    prompt_file=str(prompt_path),
                    output_file=str(output_path) if output_path else None,
                    headless=headless,
                )
            )
    except JobQueueFullError as exc:
        # Saturated pool: keep the retry hint and depth so a caller can back
        # off deliberately instead of reading a generic internal failure.
        retry_after = getattr(exc, "retry_after_sec", None)
        hint = f" (retry in {retry_after}s)" if retry_after is not None else ""
        return _fail_json(f"Worker pool is full{hint}: {exc}", "cli-429", json_output)
    except Exception as exc:
        return _fail_json(f"Job submission failed: {exc}", "cli-500", json_output)

    if response.error:
        return _fail_json(f"Job submission failed: {response.error}", "cli-500", json_output)

    record = response.record
    if record is None:
        return _fail_json("Job submission returned no record", "cli-500", json_output)
    if json_output:
        print(json.dumps({"success": True, "job_id": str(record.job_id)}, indent=2))
    else:
        print(f"{status_glyph('ok')} Job queued: {record.job_id}")
        print(f"Poll with: qwen-web-arwaky job status {record.job_id}")
    return 0


def handle_jobs_command(args: argparse.Namespace, jobs: IJobManagerAggregate) -> int:
    """Handle jobs subcommand via the IJobManagerAggregate verbs."""
    # The job subparser registers dest="job_command"; older releases read
    # args.command, so prefer whichever the parser actually set.
    command = getattr(args, "job_command", getattr(args, "command", None))
    json_output = bool(getattr(args, "json", False))

    if command == "submit":
        return _cmd_submit(args, jobs)
    if command == "list":
        limit = int(getattr(args, "limit", 10))
        response = jobs.execute(JobRequest(verb="list_jobs", limit=limit))
        if response.error:
            return _fail_json(f"Job list failed: {response.error}", "cli-500", json_output)
        records = list(response.records or [])
        if json_output:
            print(
                json.dumps(
                    {
                        "success": True,
                        "total": len(records),
                        "jobs": [
                            {
                                "job_id": r.job_id,
                                "status": _job_status(r),
                                "completed": r.completed,
                                "input_file": r.input_file,
                                "output_file": r.output_file,
                            }
                            for r in records
                        ],
                    },
                    indent=2,
                    default=str,
                )
            )
            return 0
        if not records:
            print("No jobs found. Submit one with 'qwen-web-arwaky job submit -i <prompt.md>'.")
            return 0
        print(f"{'Job ID':<36} {'Status':<12} {'Completed':<12}")
        print("-" * 60)
        for r in records:
            print(f"{str(r.job_id):<36} {_job_status(r):<12} {str(r.completed):<12}")
        return 0
    if command == "status":
        response = jobs.execute(JobRequest(verb="get_job_status", job_id=getattr(args, "job_id", None)))
        if response.error:
            return _fail_json(f"Job status failed: {response.error}", "cli-500", json_output)
        record = response.record
        if record is None:
            return _fail_json(f"Job not found: {getattr(args, 'job_id', '')}", "cli-400", json_output)
        if json_output:
            print(
                json.dumps(
                    {
                        "success": True,
                        "job_id": record.job_id,
                        "status": _job_status(record),
                        "completed": record.completed,
                    },
                    indent=2,
                    default=str,
                )
            )
            return 0
        print(f"{str(record.job_id)}: {_job_status(record)}")
        return 0
    if command == "cleanup":
        response = jobs.execute(JobRequest(verb="cleanup_stale_jobs"))
        if response.error:
            return _fail_json(f"Job cleanup failed: {response.error}", "cli-500", json_output)
        if json_output:
            print(json.dumps({"success": True, "removed": response.removed}, indent=2))
        else:
            print(f"Cleaned {response.removed} stale job(s)")
        return 0

    print("Use 'qwen-web-arwaky job --help' for usage")
    return 1


__all__ = ["handle_jobs_command"]
