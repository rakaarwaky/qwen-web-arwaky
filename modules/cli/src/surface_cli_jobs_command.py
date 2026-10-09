"""CLI surface: jobs command — manage asynchronous background prompt jobs.

Smart surface: maps parsed args to the IJobManagerAggregate verbs
(submit_file_job, submit_attachment_job, get_job_status, list_jobs) and
formats the response as a human-readable table or JSON envelope.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from modules.shared.src.contract_jobs_aggregate import IJobManagerAggregate
from modules.shared.src.taxonomy_core_vo import JobRecord
from modules.shared.src.taxonomy_jobs_vo import JobRequest


def _job_status(record: JobRecord) -> str:
    """Derive a human-readable status for a job record."""
    if not record.completed:
        return "RUNNING"
    return "FAILED" if record.error else "COMPLETED"


def _format_job_row(record: JobRecord) -> str:
    """Format one job record as a table row."""
    status = _job_status(record)
    input_file = (record.input_file or "-")[:30]
    output_file = (record.output_file or "-")[:30]
    duration = f"{record.duration_sec}s" if record.duration_sec else "-"
    error = (record.error or "")[:40]
    return f"{record.job_id:<40} {status:<10} {input_file:<30} {output_file:<30} {duration:<8} {error}"


def _cmd_submit(args: argparse.Namespace, jobs: IJobManagerAggregate) -> int:
    """Submit a file or attachment prompt job to the background worker pool."""
    prompt_path = args.prompt_path
    attachment = getattr(args, "attachment_path", None)
    output_path = getattr(args, "output_path", None)
    headless = bool(getattr(args, "headless", True))

    # Resolve role templates to materialized paths.
    from modules.shared.src.utility_core_prompt_template import is_prompt_role, materialize_role_template

    if is_prompt_role(prompt_path):
        prompt_path = str(materialize_role_template(prompt_path))

    if attachment:
        request = JobRequest(
            verb="submit_attachment_job",
            prompt_file=prompt_path,
            attachment_file=attachment,
            output_file=output_path,
            headless=headless,
        )
    else:
        request = JobRequest(
            verb="submit_file_job",
            prompt_file=prompt_path,
            output_file=output_path,
            headless=headless,
        )

    try:
        response = jobs.execute(request)
    except Exception as exc:
        print(f"[ERROR] Job submission failed: {exc}", file=sys.stderr)
        return 1

    record = response.record
    if record is None:
        print(f"[ERROR] Job submission returned no record: {response.error}")
        return 1

    json_output = bool(getattr(args, "json", False))
    if json_output:
        print(
            json.dumps(
                {
                    "success": True,
                    "status": "ACCEPTED",
                    "job_id": record.job_id,
                    "latest_event": record.latest_event,
                    "completed": record.completed,
                    "created_at": record.created_at,
                    "input_file": record.input_file,
                    "output_file": record.output_file,
                    "message": "Job submitted. Poll with 'qwen-web-arwaky jobs status <job_id>'.",
                },
                indent=2,
                default=str,
            )
        )
    else:
        print(f"✅ Job submitted: {record.job_id}")
        print(f"   Input:    {record.input_file}")
        print(f"   Output:   {record.output_file or '(default)'}")
        print(f"   Status:   {record.latest_event or 'QUEUED'}")
        print(f"   Poll with: qwen-web-arwaky jobs status {record.job_id}")
    return 0


def _cmd_status(args: argparse.Namespace, jobs: IJobManagerAggregate) -> int:
    """Query the status of a specific job."""
    job_id = args.job_id
    response = jobs.execute(JobRequest(verb="get_job_status", job_id=job_id))
    record = response.record
    json_output = bool(getattr(args, "json", False))

    if record is None:
        msg = f"Job not found: {job_id}"
        if json_output:
            print(json.dumps({"success": False, "error": msg}, indent=2))
        else:
            print(f"❌ {msg}")
        return 1

    if json_output:
        print(
            json.dumps(
                {
                    "success": True,
                    "status": _job_status(record),
                    "job_id": record.job_id,
                    "latest_event": record.latest_event,
                    "completed": record.completed,
                    "created_at": record.created_at,
                    "started_at": record.started_at,
                    "completed_at": record.completed_at,
                    "duration_sec": record.duration_sec,
                    "input_file": record.input_file,
                    "attachment_file": record.attachment_file,
                    "output_file": record.output_file,
                    "error": record.error,
                    "result_preview": record.result_preview,
                },
                indent=2,
                default=str,
            )
        )
    else:
        print(f"📊 Job: {record.job_id}")
        print(f"   Status:      {_job_status(record)}")
        print(f"   Event:       {record.latest_event or '-'}")
        print(f"   Created:     {record.created_at}")
        if record.completed_at:
            print(f"   Completed:   {record.completed_at}")
        if record.duration_sec:
            print(f"   Duration:    {record.duration_sec}s")
        print(f"   Input:       {record.input_file or '-'}")
        if record.attachment_file:
            print(f"   Attachment:  {record.attachment_file}")
        print(f"   Output:      {record.output_file or '(default)'}")
        if record.error:
            print(f"   Error:       {record.error}")
        if record.result_preview:
            print(f"   Preview:     {record.result_preview[:200]}")
    return 0


def _cmd_list(args: argparse.Namespace, jobs: IJobManagerAggregate) -> int:
    """List recent background jobs."""
    limit = int(getattr(args, "limit", 10))
    response = jobs.execute(JobRequest(verb="list_jobs", limit=limit))
    records = response.records or []
    json_output = bool(getattr(args, "json", False))

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
                            "latest_event": r.latest_event,
                            "completed": r.completed,
                            "created_at": r.created_at,
                            "completed_at": r.completed_at,
                            "duration_sec": r.duration_sec,
                            "input_file": r.input_file,
                            "attachment_file": r.attachment_file,
                            "output_file": r.output_file,
                            "error": r.error,
                        }
                        for r in records
                    ],
                },
                indent=2,
                default=str,
            )
        )
    else:
        if not records:
            print("No jobs found. Submit one with 'qwen-web-arwaky jobs submit -i <prompt.md>'.")
            return 0
        print(f"📊 Recent Jobs ({len(records)})")
        print("─" * 110)
        print(f"{'JOB ID':<40} {'STATUS':<10} {'INPUT':<30} {'OUTPUT':<30} {'DURATION':<8} {'ERROR'}")
        print("─" * 110)
        for r in records:
            print(_format_job_row(r))
        print("─" * 110)
    return 0


def _cmd_cleanup(args: argparse.Namespace, storage: Any) -> int:
    """Remove stale job records past their retention window."""
    json_output = bool(getattr(args, "json", False))
    try:
        removed = storage.cleanup_stale_jobs()
        if json_output:
            print(json.dumps({"success": True, "removed": removed}, indent=2))
        else:
            print(f"✅ Cleanup complete: {removed} stale job record(s) removed.")
        return 0
    except Exception as exc:
        if json_output:
            print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        else:
            print(f"[ERROR] Cleanup failed: {exc}", file=sys.stderr)
        return 1


def handle(args: argparse.Namespace, jobs: IJobManagerAggregate, storage: Any = None) -> int:
    """Dispatch the jobs subcommand to the matching handler."""
    verb = getattr(args, "job_command", None)
    if verb == "submit":
        return _cmd_submit(args, jobs)
    if verb == "status":
        return _cmd_status(args, jobs)
    if verb == "list":
        return _cmd_list(args, jobs)
    if verb == "cleanup":
        if storage is None:
            print("[ERROR] Job storage not available for cleanup.", file=sys.stderr)
            return 1
        return _cmd_cleanup(args, storage)
    print("Use 'qwen-web-arwaky jobs --help' for usage")
    return 1


__all__ = ["handle"]
