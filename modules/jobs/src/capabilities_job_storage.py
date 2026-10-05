"""Capabilities: job persistence and state storage (AES403).

Implements IJobStorageProtocol.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.shared.src.contract_jobs_protocol import IJobStorageProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_JOBS_DIR
from modules.shared.src.taxonomy_core_vo import (
    JobId,
    JobLimit,
    JobPath,
    JobPreview,
    JobRecord,
    Pid,
    ResultText,
)
from modules.shared.src.taxonomy_jobs_vo import JobCount
from modules.shared.src.utility_io_writer import ATOMIC_TEMP_SUFFIX, atomic_write_text
from modules.shared.src.utility_logger_factory import get_logger

log = get_logger("capabilities_job_storage")

#: Anything outside this set is replaced before a job ID touches the filesystem.
_unsafe_filename_chars = re.compile(r"[^A-Za-z0-9_.\-]")
#: Leaves room for the ``.json`` extension under a 255-byte NAME_MAX.
_max_job_filename_len = 200


# Block 1: Class Definition & Constructor


class JobStorage(IJobStorageProtocol):
    """File-backed job state persistence adhering to XDG state specification."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or DEFAULT_JOBS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_stale_jobs()
        self.reconcile_zombies()

    # Block 2: Protocol Method Implementation

    def save_job(self, record: JobRecord) -> None:
        """Persist a job record to an atomic JSON file."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        target = self._job_file_path(record.job_id)
        data = asdict(record)
        content = json.dumps(data, indent=2)
        atomic_write_text(target, content)
        log.debug("job_saved", job_id=record.job_id, latest_event=record.latest_event, completed=record.completed)

    def current_pid(self) -> Pid:
        """Return the PID that owns the records written from this process."""
        return Pid(os.getpid())

    def resolve_job_path(self, raw_path: JobPath) -> JobPath:
        """Return the absolute path a job's *raw_path* argument names."""
        return JobPath(Path(raw_path.path).expanduser().resolve())

    def preview_job_output(self, output_path: JobPath, result_text: ResultText) -> JobPreview:
        """Read a short preview of the output file, falling back to the result text."""
        target = Path(output_path.path)
        fallback = result_text.text[:500] if result_text.text else None
        if target.exists():
            try:
                return JobPreview(target.read_text(encoding="utf-8")[:500])
            except OSError:
                return JobPreview(fallback)
        return JobPreview(fallback)

    def get_job(self, job_id: JobId | str) -> JobRecord | None:
        """Retrieve a job record by ID."""
        target = self._job_file_path(job_id)
        if not target.exists():
            return None
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            return JobRecord(
                job_id=raw["job_id"],
                created_at=raw["created_at"],
                latest_event=raw.get("latest_event"),
                completed=bool(raw.get("completed", False)),
                started_at=raw.get("started_at"),
                completed_at=raw.get("completed_at"),
                duration_sec=raw.get("duration_sec"),
                input_file=raw.get("input_file"),
                attachment_file=raw.get("attachment_file"),
                output_file=raw.get("output_file"),
                owner_pid=raw.get("owner_pid"),
                heartbeat_at=raw.get("heartbeat_at"),
                error=raw.get("error"),
                result_preview=raw.get("result_preview"),
            )
        except Exception as exc:
            log.error("job_read_failed", job_id=str(job_id), error=str(exc))
            return None

    def reconcile_zombies(self) -> JobCount:
        """Mark started-but-incomplete records owned by dead processes as failed."""
        import os

        reconciled = 0
        for path in self.storage_dir.glob("*.json"):
            if path.name.endswith(ATOMIC_TEMP_SUFFIX):
                continue
            rec = self.get_job(path.stem)
            if rec is None or rec.completed or rec.owner_pid is None:
                continue
            alive = True
            try:
                os.kill(rec.owner_pid, 0)
            except OSError:
                alive = False
            if not alive:
                updated = JobRecord(
                    job_id=rec.job_id,
                    created_at=rec.created_at,
                    latest_event=rec.latest_event,
                    completed=True,
                    started_at=rec.started_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    duration_sec=rec.duration_sec,
                    input_file=rec.input_file,
                    attachment_file=rec.attachment_file,
                    output_file=rec.output_file,
                    owner_pid=rec.owner_pid,
                    heartbeat_at=rec.heartbeat_at,
                    error="process exited before completion",
                    result_preview=rec.result_preview,
                )
                self.save_job(updated)
                reconciled += 1
        return JobCount(reconciled)

    def cleanup_stale_jobs(
        self,
        *,
        terminal_ttl_hours: float = 24.0,
        incomplete_ttl_days: float = 7.0,
    ) -> int:
        """Delete terminal jobs after 24h and abandoned jobs after 7 days.

        Cleanup is explicit and deterministic so MCP startup/maintenance can
        invoke it without changing the semantics of status reads.
        """
        reference = datetime.now(timezone.utc)
        terminal_ttl = timedelta(hours=terminal_ttl_hours)
        incomplete_ttl = timedelta(days=incomplete_ttl_days)
        removed = 0
        for path in self.storage_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                stamp = raw.get("completed_at") if raw.get("completed") else raw.get("created_at")
                created = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                ttl = terminal_ttl if raw.get("completed") else incomplete_ttl
                if reference - created > ttl:
                    path.unlink(missing_ok=True)
                    removed += 1
            except (OSError, ValueError, TypeError, KeyError):
                continue
        return removed

    def list_jobs(self, limit: JobLimit = JobLimit(10)) -> list[JobRecord]:
        """List recently recorded jobs sorted newest to oldest.

        Best-effort under concurrent writes. Records are persisted with
        ``atomic_write_text``, whose ``os.replace`` is atomic on POSIX, so a
        reader never observes a half-written file. A job deleted between the
        directory scan and its read is simply skipped, which can make the result
        shorter than ``limit``; callers must not treat the length as a count of
        stored jobs.
        """
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        records: list[JobRecord] = []
        candidate_files: list[tuple[float, Path]] = []
        for path in self.storage_dir.glob("*.json"):
            if path.name.endswith(ATOMIC_TEMP_SUFFIX):
                continue
            try:
                candidate_files.append((path.stat().st_mtime, path))
            except OSError:
                continue
        candidate_files.sort(key=lambda t: t[0], reverse=True)
        for _, path in candidate_files[: int(limit)]:
            job_id = path.stem
            rec = self.get_job(job_id)
            if rec is not None:
                records.append(rec)
        return records

    # Block 3: Dunder Methods, Factories & Helpers

    def _job_file_path(self, job_id: JobId | str) -> Path:
        """Map a job ID onto a filesystem-safe path inside the storage dir.

        Job IDs are generated internally, but ``get_job_status`` accepts one
        straight from an MCP caller, so treat the value as untrusted: collapse
        every character outside ``[A-Za-z0-9_.-]`` (covers path separators,
        ``:*?"<>|`` on Windows, and control bytes) and cap the length well below
        NAME_MAX, appending a digest so truncated IDs stay distinct.
        """
        raw = str(job_id)
        clean_id = _unsafe_filename_chars.sub("_", raw)
        if len(clean_id) > _max_job_filename_len:
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
            clean_id = f"{clean_id[: _max_job_filename_len - len(digest) - 1]}_{digest}"
        return self.storage_dir / f"{clean_id}.json"
