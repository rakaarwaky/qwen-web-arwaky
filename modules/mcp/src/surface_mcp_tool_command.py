"""MCP surface: tool handlers (AES406).

Smart surface: tools delegating to individual agent contracts over stdio JSON-RPC.
Includes structured JSON response formatting, path normalization, pre-flight validation,
and session management tools (check_session, delete_session).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    JobId,
    PromptText,
    TimeoutSec,
)
from modules.shared.src.utility_core_response import detect_processing_failure


def _check_execution_result(res_str: str) -> str | None:
    fail_msg = detect_processing_failure(res_str)
    if fail_msg:
        code = "AUTH_REQUIRED" if "AUTH_REQUIRED" in fail_msg else "EXECUTION_ERROR"
        hint = (
            "Session expired or not authenticated. Call setup_session tool to log in."
            if code == "AUTH_REQUIRED"
            else "Execution failed on core pipeline."
        )
        return _format_error_payload(code=code, message=fail_msg, hint=hint, retryable=True)
    return None


def _format_success_payload(
    result_text: str,
    output_path: str | None = None,
    run_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Format successful MCP tool response into structured JSON string."""
    err = _check_execution_result(result_text)
    if err:
        return err

    payload: dict[str, Any] = {
        "success": True,
        "status": "SUCCESS",
        "result": result_text,
    }
    if output_path:
        payload["output_path"] = output_path
    if run_id:
        payload["run_id"] = run_id
    if extra:
        payload.update(extra)
    return json.dumps(payload, indent=2)


def _format_error_payload(
    code: str,
    message: str,
    hint: str,
    retryable: bool = False,
    field: str | None = None,
) -> str:
    """Format failed MCP tool response into structured JSON string."""
    err: dict[str, Any] = {
        "code": code,
        "message": message,
        "hint": hint,
        "retryable": retryable,
    }
    if field:
        err["field"] = field
    return json.dumps({"success": False, "error": err}, indent=2)


class McpToolCommand:
    """MCP tool dispatcher — delegates to individual agent aggregate contracts."""

    def __init__(
        self,
        direct: IDirectPromptAggregate,
        file_only: IPromptFileAggregate,
        attachment: IAttachmentPromptAggregate,
        session: ISessionAggregate,
        setup: ISetupAggregate,
        workspace: IWorkspaceProtocol,
        jobs: IJobManagerAggregate | None = None,
    ) -> None:
        """Inject individual agent aggregate contracts."""
        self._direct = direct
        self._file_only = file_only
        self._attachment = attachment
        self._session = session
        self._setup = setup
        self._workspace = workspace
        self._jobs = jobs

    def process_direct_prompt(self, prompt: str, timeout_sec: int = 120, headless: bool = True) -> str:
        """Process a direct text prompt string to chat.qwen.ai.

        Args:
            prompt: Direct text prompt to send to Qwen.
            timeout_sec: Maximum seconds to wait for assistant response (default: 120s).
            headless: Run browser headlessly (default: True).

        Returns:
            JSON string containing success status, assistant response text, and metadata.
        """
        if not prompt or not prompt.strip():
            return _format_error_payload(
                code="VALIDATION_ERROR",
                message="prompt text must not be empty.",
                hint="Provide a valid non-empty prompt string.",
                field="prompt",
            )

        try:
            res = self._direct.process_direct_prompt(
                PromptText(prompt), TimeoutSec(timeout_sec), headless=HeadlessFlag(headless)
            )
            return _format_success_payload(str(res))
        except Exception as exc:
            return _format_error_payload(
                code="EXECUTION_ERROR",
                message=str(exc),
                hint="Verify network connectivity and session login status.",
                retryable=True,
            )

    def process_prompt_file_only(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
        async_run: bool = True,
    ) -> str:
        """Process a single Markdown prompt file from disk without attachment.

        Args:
            input_file: Path to Markdown prompt file.
            output_file: Optional output file destination path.
            headless: Run browser headlessly (default: True).
            async_run: Run job asynchronously in background to avoid MCP timeout (default: True).

        Returns:
            JSON string containing success status, resolved output path, and result preview (or job_id if async).
        """
        p_path = Path(input_file).expanduser().resolve()
        if not p_path.exists():
            return _format_error_payload(
                code="FILE_NOT_FOUND",
                message=f"Prompt file not found: {p_path}",
                hint="Check prompt_file path or use init_workspace tool.",
                field="input_file",
            )

        out_path = Path(output_file).expanduser().resolve() if output_file else None

        if async_run and self._jobs is not None:
            try:
                record = self._jobs.submit_file_job(
                    prompt_file=FilePath(p_path),
                    output_file=FilePath(out_path) if out_path else None,
                    headless=HeadlessFlag(headless),
                )
                return json.dumps(
                    {
                        "success": True,
                        "job_id": record.job_id,
                        "latest_event": record.latest_event,
                        "completed": record.completed,
                        "created_at": record.created_at,
                        "input_file": record.input_file,
                        "output_file": record.output_file,
                        "message": "Prompt processing job submitted in background. Poll with get_job_status.",
                    },
                    indent=2,
                )
            except Exception as exc:
                return _format_error_payload(
                    code="JOB_SUBMIT_FAILED",
                    message=str(exc),
                    hint="Failed to schedule asynchronous job.",
                    retryable=True,
                )

        try:
            res = self._file_only.process_prompt_file_only(
                FilePath(p_path),
                FilePath(out_path) if out_path else None,
                HeadlessFlag(headless),
            )
            return _format_success_payload(
                result_text=str(res),
                output_path=str(out_path) if out_path else None,
            )
        except Exception as exc:
            return _format_error_payload(
                code="EXECUTION_ERROR",
                message=str(exc),
                hint="Ensure Chromium browser and valid session are available.",
                retryable=True,
            )

    def process_prompt_with_attachment(
        self,
        prompt_file: str,
        attachment_file: str,
        output_file: str | None = None,
        headless: bool = True,
        async_run: bool = True,
    ) -> str:
        """Process a Markdown prompt file with a document attachment.

        Args:
            prompt_file: Path to Markdown prompt file.
            attachment_file: Path to document attachment file (PDF, TXT, MD).
            output_file: Optional output file destination path.
            headless: Run browser headlessly (default: True).
            async_run: Run job asynchronously in background to avoid MCP timeout (default: True).

        Returns:
            JSON string containing success status, resolved output path, and result (or job_id if async).
        """
        p_path = Path(prompt_file).expanduser().resolve()
        if not p_path.exists():
            return _format_error_payload(
                code="FILE_NOT_FOUND",
                message=f"Prompt file not found: {p_path}",
                hint="Check prompt_file path.",
                field="prompt_file",
            )

        a_path = Path(attachment_file).expanduser().resolve()
        if not a_path.exists():
            return _format_error_payload(
                code="FILE_NOT_FOUND",
                message=f"Attachment file not found: {a_path}",
                hint="Check attachment_file path.",
                field="attachment_file",
            )

        out_path = Path(output_file).expanduser().resolve() if output_file else None

        if async_run and self._jobs is not None:
            try:
                record = self._jobs.submit_attachment_job(
                    prompt_file=FilePath(p_path),
                    attachment_file=FilePath(a_path),
                    output_file=FilePath(out_path) if out_path else None,
                    headless=HeadlessFlag(headless),
                )
                return json.dumps(
                    {
                        "success": True,
                        "job_id": record.job_id,
                        "latest_event": record.latest_event,
                        "completed": record.completed,
                        "created_at": record.created_at,
                        "input_file": record.input_file,
                        "attachment_file": record.attachment_file,
                        "output_file": record.output_file,
                        "message": "Attachment job submitted in background. Poll with get_job_status.",
                    },
                    indent=2,
                )
            except Exception as exc:
                return _format_error_payload(
                    code="JOB_SUBMIT_FAILED",
                    message=str(exc),
                    hint="Failed to schedule asynchronous job.",
                    retryable=True,
                )

        try:
            res = self._attachment.process_prompt_with_attachment(
                FilePath(p_path),
                FilePath(a_path),
                FilePath(out_path) if out_path else None,
                HeadlessFlag(headless),
            )
            return _format_success_payload(
                result_text=str(res),
                output_path=str(out_path) if out_path else None,
            )
        except Exception as exc:
            return _format_error_payload(
                code="EXECUTION_ERROR",
                message=str(exc),
                hint="Ensure attachment format is supported by Qwen Web.",
                retryable=True,
            )

    def get_job_status(self, job_id: str) -> str:
        """Query status and details of a background prompt processing job.

        Args:
            job_id: The job ID returned when the prompt was submitted.

        Returns:
            JSON string containing job status, progress, timing, and result preview.
        """
        if not job_id or not job_id.strip():
            return _format_error_payload(
                code="VALIDATION_ERROR",
                message="job_id must not be empty.",
                hint="Provide a valid job_id string.",
                field="job_id",
            )

        if self._jobs is None:
            return _format_error_payload(
                code="SERVICE_UNAVAILABLE",
                message="Job manager is not configured.",
                hint="Check MCP server setup.",
            )

        record = self._jobs.get_job_status(JobId(job_id))
        if record is None:
            return _format_error_payload(
                code="JOB_NOT_FOUND",
                message=f"Job not found: {job_id}",
                hint="Verify the job_id or use list_jobs tool.",
                field="job_id",
            )

        payload: dict[str, Any] = {
            "success": True,
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
        }
        return json.dumps(payload, indent=2)

    def list_jobs(self, limit: int = 10) -> str:
        """List recently submitted background prompt processing jobs.

        Args:
            limit: Maximum number of recent jobs to return (default: 10).

        Returns:
            JSON string containing a list of job records.
        """
        if limit < 1:
            return _format_error_payload(
                code="VALIDATION_ERROR",
                message=f"limit must be greater than or equal to 1, got {limit}.",
                hint="Provide a positive integer limit (e.g. limit=10).",
                field="limit",
            )

        if self._jobs is None:
            return _format_error_payload(
                code="SERVICE_UNAVAILABLE",
                message="Job manager is not configured.",
                hint="Check MCP server setup.",
            )

        records = self._jobs.list_jobs(limit=limit)
        items = [
            {
                "job_id": rec.job_id,
                "latest_event": rec.latest_event,
                "completed": rec.completed,
                "created_at": rec.created_at,
                "completed_at": rec.completed_at,
                "duration_sec": rec.duration_sec,
                "input_file": rec.input_file,
                "attachment_file": rec.attachment_file,
                "output_file": rec.output_file,
                "error": rec.error,
            }
            for rec in records
        ]
        return json.dumps({"success": True, "total": len(items), "jobs": items}, indent=2)

    def check_session(self) -> str:
        """Check status and validity of saved browser session tokens.

        Returns:
            JSON string with session_valid flag and recommended next action.
        """
        try:
            valid, msg = self._session.validate_session()
            return json.dumps(
                {
                    "success": True,
                    "session_valid": bool(valid),
                    "message": str(msg),
                    "next_action": None if valid else "setup_session",
                },
                indent=2,
            )
        except Exception as exc:
            return _format_error_payload(
                code="SESSION_CHECK_FAILED",
                message=str(exc),
                hint="Call setup_session to log in manually.",
            )

    def delete_session(self, confirm: bool = False) -> str:
        """Delete saved browser session tokens. Requires confirm=True.

        Args:
            confirm: Must be explicitly set to True to confirm session deletion.

        Returns:
            JSON string confirming deletion or warning if confirm=False.
        """
        if not confirm:
            return _format_error_payload(
                code="CONFIRMATION_REQUIRED",
                message="Deleting session tokens requires explicit confirm=True.",
                hint="Call delete_session(confirm=True) to proceed.",
            )

        try:
            self._session.delete_session()
            return json.dumps(
                {
                    "success": True,
                    "message": "Saved browser session tokens deleted successfully.",
                    "next_action": "setup_session",
                },
                indent=2,
            )
        except Exception as exc:
            return _format_error_payload(
                code="SESSION_DELETE_FAILED",
                message=str(exc),
                hint="Check filesystem write permissions for session directory.",
            )

    def setup_session(self) -> str:
        """Launch visible browser on chat.qwen.ai for manual login / session setup.

        Returns:
            JSON string with setup result message.
        """
        try:
            res = self._setup.setup_session()
            return _format_success_payload(str(res))
        except Exception as exc:
            return _format_error_payload(
                code="SETUP_SESSION_FAILED",
                message=str(exc),
                hint="Ensure Chromium browser dependencies are installed.",
            )

    def init_workspace(self, target_dir: str = ".") -> str:
        """Initialize workspace directory structure and SKILL.md guide.

        Args:
            target_dir: Target directory path (default: ".").

        Returns:
            JSON string confirming workspace initialization.
        """
        t_path = Path(target_dir).expanduser().resolve()
        try:
            self._workspace.init_workspace(FilePath(t_path))
            return json.dumps(
                {
                    "success": True,
                    "message": f"Workspace initialized successfully at {t_path}",
                    "workspace_path": str(t_path),
                },
                indent=2,
            )
        except Exception as exc:
            return _format_error_payload(
                code="INIT_WORKSPACE_FAILED",
                message=str(exc),
                hint="Check write permissions for target_dir.",
            )
