"""Jobs-domain value objects and aggregate request/response pair.

``JobRequest`` and ``JobResponse`` are the single pair the aggregate's
``execute`` accepts and returns, so consumers depend on one stable seam.
Operation-specific arguments and results live on those two VOs rather than
being spread across several aggregate methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NewType

from modules.shared.src.taxonomy_core_vo import (
    AttachmentPath,
    JobId,
    JobLimit,
    JobRecord,
    OutputPath,
    PromptPath,
)

#: Number of stale or zombie job records a cleanup pass removed or repaired.
JobCount = NewType("JobCount", int)

#: Hours a terminal job record is retained before cleanup removes it.
TtlHours = NewType("TtlHours", float)

#: Days an abandoned (never-completed) job record is retained.
TtlDays = NewType("TtlDays", float)

#: The persisted records a listing verb returned, newest first.
#: Declared as a NewType so the contract signature carries one named
#: domain type rather than a bare list primitive (AES402).
JobList = NewType("JobList", list[JobRecord])

#: Which job operation a ``JobRequest`` asks for. The agent behind
#: ``IJobManagerAggregate`` routes each one to the matching capability.
JobVerb = Literal[
    "submit_file_job",
    "submit_attachment_job",
    "get_job_status",
    "list_jobs",
    "shutdown",
]


@dataclass(frozen=True)
class JobRequest:
    """One job verb plus everything the agent needs to run it.

    Fields the chosen verb does not read stay at their defaults, so a file
    job and an attachment job share one shape without either one passing
    arguments the other ignores.
    """

    verb: JobVerb
    prompt_file: Path | PromptPath | str = ""
    attachment_file: Path | AttachmentPath | str | None = None
    output_file: Path | OutputPath | str | None = None
    headless: bool = True
    job_id: JobId | str | None = None
    limit: JobLimit | int = JobLimit(10)
    force: bool = False
    terminal_ttl_hours: float = 24.0
    incomplete_ttl_days: float = 7.0


@dataclass(frozen=True)
class JobResponse:
    """What a job verb produced.

    ``record`` carries the persisted ``JobRecord`` for submission/status/list
    verbs; ``removed`` reports the count for shutdown/cleanup. ``error``
    carries any failure reason.
    """

    record: JobRecord | None = None
    records: list[JobRecord] | None = None
    removed: int = 0
    error: str | None = None


__all__ = [
    "JobCount",
    "JobList",
    "JobRequest",
    "JobResponse",
    "JobVerb",
    "TtlDays",
    "TtlHours",
]
