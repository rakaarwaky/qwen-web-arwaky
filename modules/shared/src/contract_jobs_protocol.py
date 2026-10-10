"""Jobs-domain capability contracts (AES102 `_protocol`).

One file for the jobs feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IJobStorageProtocol``         → ``JobStorage``             (persist / read jobs / preview)

The outward export surface for outer layers is ``IJobManagerAggregate`` in
``contract_jobs_aggregate.py``, whose single ``execute`` takes a ``JobRequest``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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


class IJobStorageProtocol(ABC):
    """Job persistence and state storage contract."""

    @abstractmethod
    def save_job(self, record: JobRecord) -> None:
        """Persist a job record to disk."""
        ...

    @abstractmethod
    def get_job(self, job_id: JobId | str) -> JobRecord | None:
        """Retrieve a job record by ID."""
        ...

    @abstractmethod
    def current_pid(self) -> Pid:
        """Return the PID that owns the records written from this process.

        The submit path stamps this onto ``owner_pid`` so a later
        :meth:`reconcile_zombies` can tell a crashed run from a live one.
        """
        ...

    @abstractmethod
    def preview_job_output(self, output_path: JobPath, result_text: ResultText) -> JobPreview:
        """Return a short preview of the file at *output_path*.

        Reads the first 500 characters of the output file when it exists;
        otherwise falls back to the supplied *result_text* (or None when
        that is empty too). The filesystem read lives here, not in the
        orchestrator.
        """
        ...

    @abstractmethod
    def resolve_job_path(self, raw_path: JobPath) -> JobPath:
        """Return the absolute path a job's *raw_path* argument names.

        A job's prompt, attachment, and output arguments arrive as plain
        strings from the CLI and MCP layers, so this expands ``~`` and
        anchors the result against the process working directory.
        """
        ...

    @abstractmethod
    def list_jobs(self, limit: JobLimit = JobLimit(10)) -> list[JobRecord]:
        """List recently recorded jobs sorted newest to oldest."""
        ...

    @abstractmethod
    def reconcile_zombies(self) -> JobCount:
        """Mark started-but-incomplete records owned by dead processes as failed.

        Return the number of records reconciled.
        """
        ...

    @abstractmethod
    def cleanup_stale_jobs(
        self,
        *,
        terminal_ttl_hours: float = 24.0,
        incomplete_ttl_days: float = 7.0,
    ) -> int:
        """Delete terminal jobs past *terminal_ttl_hours* and abandoned jobs past
        *incomplete_ttl_days*, measured against *now*.

        Return the number of records removed.
        """
        ...


__all__ = [
    "IJobStorageProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IJobStorageProtocol": IJobStorageProtocol,
}
