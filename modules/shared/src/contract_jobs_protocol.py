"""Jobs-domain capability contracts (AES102 `_protocol`).

One file for the jobs feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IJobStorageProtocol``         → ``JobStorage``             (persist / read jobs)
- ``IFolderCompileProtocol``      → ``FolderCompiler``         (compile folder → markdown)
- ``IFolderToAttachmentProtocol`` → ``FolderToAttachmentAdapter`` (resolve path → attachment file)
- ``IStatusProtocol``            → ``StatusFileWriter``        (write / read status JSON)

The outward export surface for outer layers is ``IJobManagerAggregate`` in
``contract_jobs_aggregate.py``, whose single ``execute`` takes a ``JobRequest``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from modules.shared.src.taxonomy_core_constant import MAX_FOLDER_DEPTH, MAX_IMPORT_DEPTH
from modules.shared.src.taxonomy_core_vo import (
    CompileDepth,
    JobId,
    JobLimit,
    JobRecord,
    StatusRecordMap,
    StatusRecordVO,
)
from modules.shared.src.taxonomy_jobs_vo import JobCount


class IJobStorageProtocol(ABC):
    """Job persistence and state storage contract."""

    @abstractmethod
    def save_job(self, record: JobRecord) -> None:
        """Persist a job record to disk."""
        ...

    @abstractmethod
    def get_job(self, job_id: JobId) -> JobRecord | None:
        """Retrieve a job record by ID."""
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


class IFolderCompileProtocol(ABC):
    """Folder-to-markdown compilation capability contract."""

    @abstractmethod
    def compile_folder(
        self,
        folder_path: Path,
        output_path: Path | None = None,
        max_depth: CompileDepth = CompileDepth(MAX_FOLDER_DEPTH),
        import_depth: CompileDepth = CompileDepth(MAX_IMPORT_DEPTH),
        include_imports: bool = True,
        boundary_root: Path | None = None,
    ) -> Path:
        """Compile folder contents to a single markdown file.

        Args:
            folder_path: Directory to compile.
            output_path: Optional output file path. Auto-generated if None.
            max_depth: Maximum recursion depth.
            import_depth: Maximum number of hops for resolving external
                imports/links beyond the first-hop files linked from the
                folder.  With the default of 1, only files linked directly
                from in-folder documents are included; transitive
                (second-hop) links are not followed.
            include_imports: Follow imports/links of folder files and include
                external dependencies (cycle-safe, bounded hops).
            boundary_root: Confinement boundary for import resolution.
                Resolved imports outside this root are refused because the
                compiled output is uploaded to a third-party service.
                Defaults to the ``QWEN_WORKSPACE_ROOT`` env var when set
                (matching the MCP workspace boundary), else the scanned
                folder's parent.

        Returns:
            Path to the compiled markdown file.
        """
        ...

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory (not a file)."""
        ...


class IFolderToAttachmentProtocol(ABC):
    """Folder-to-attachment resolution capability contract."""

    @abstractmethod
    def resolve_to_attachment(
        self,
        path: Path,
        max_depth: CompileDepth = CompileDepth(MAX_FOLDER_DEPTH),
        import_depth: CompileDepth = CompileDepth(MAX_IMPORT_DEPTH),
    ) -> Path:
        """Resolve a path to an attachment-ready file (compile folders to markdown)."""
        ...

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory (not a file)."""
        ...


class IStatusProtocol(ABC):
    """Status file write/read capability contract."""

    @abstractmethod
    def write(self, **kwargs: Any) -> None:
        """Atomically write status to disk from the supplied record fields."""
        ...

    @abstractmethod
    def write_record(self, record: StatusRecordVO) -> None:
        """Atomically write a typed record to disk."""
        ...

    @abstractmethod
    def read(self) -> StatusRecordMap | None:
        """Read and return the current status record."""
        ...


__all__ = [
    "IJobStorageProtocol",
    "IFolderCompileProtocol",
    "IFolderToAttachmentProtocol",
    "IStatusProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IJobStorageProtocol": IJobStorageProtocol,
    "IFolderCompileProtocol": IFolderCompileProtocol,
    "IFolderToAttachmentProtocol": IFolderToAttachmentProtocol,
    "IStatusProtocol": IStatusProtocol,
}
