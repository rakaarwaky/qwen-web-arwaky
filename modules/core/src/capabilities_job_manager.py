"""Capabilities: job persistence and state management (AES403).

Implements IJobStorageProtocol.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from modules.core.src.utility_core_io_writer import atomic_write_text
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import IJobStorageProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_JOBS_DIR
from modules.shared.src.taxonomy_core_vo import (
    JobId,
    JobLimit,
    JobRecord,
)

log = get_logger("capabilities_job_manager")


class JobManager(IJobStorageProtocol):
    """File-backed job state manager adhering to XDG state specification."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or DEFAULT_JOBS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _job_file_path(self, job_id: JobId | str) -> Path:
        clean_id = str(job_id).replace("/", "_").replace("\\", "_")
        return self.storage_dir / f"{clean_id}.json"

    def save_job(self, record: JobRecord) -> None:
        """Persist a job record to an atomic JSON file."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        target = self._job_file_path(record.job_id)
        data = asdict(record)
        content = json.dumps(data, indent=2)
        atomic_write_text(target, content)
        log.debug("job_saved", job_id=record.job_id, latest_event=record.latest_event, completed=record.completed)

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
                prompt_text=raw.get("prompt_text"),
                error=raw.get("error"),
                result_preview=raw.get("result_preview"),
            )
        except Exception as exc:
            log.error("job_read_failed", job_id=str(job_id), error=str(exc))
            return None

    def list_jobs(self, limit: JobLimit | int = JobLimit(10)) -> list[JobRecord]:
        """List recently recorded jobs sorted newest to oldest."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        records: list[JobRecord] = []
        files = sorted(self.storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files[:limit]:
            job_id = path.stem
            rec = self.get_job(job_id)
            if rec is not None:
                records.append(rec)
        return records
