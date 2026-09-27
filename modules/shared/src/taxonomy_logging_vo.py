"""Logging-domain value objects, aggregate pair, and metrics snapshot.

The logging feature answers three kinds of question. *Setup* questions
ask which observability stack to install; *report* questions ask what the
run did (status file, quality report); *metrics* questions ask how often
a counter moved. The aggregate carries the first two as one
``ObservabilityRequest`` / ``ObservabilityResponse`` pair so a consumer
has one seam, and the metrics capability returns a ``MetricsSnapshot``
rather than a bare dict so a contract signature names a domain type.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, NewType, TypeAlias

from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    Mode,
    RunId,
)

#: Which observability operation an ``ObservabilityRequest`` asks for. The
#: agent behind ``IObservabilityAggregate`` routes each one to the
#: capability method that performs it.
ObservabilityVerb: TypeAlias = Literal[
    "setup_observability",
    "write_status",
    "write_quality_report",
]

#: The counter totals a ``MetricsSnapshot`` carries, keyed by counter name.
MetricsCounters: TypeAlias = Mapping[str, int]

#: Rolling-24h execution totals reported alongside the counters.
ExecutionTotal = NewType("ExecutionTotal", int)


@dataclass(frozen=True)
class MetricsSnapshot:
    """Every counter plus the rolling-24h execution totals, at read time.

    ``success_rate`` is ``None`` when no execution has been recorded, which
    is distinct from a rate of ``0.0`` (every recorded run failed).
    """

    counters: MetricsCounters = field(default_factory=dict)
    total_executions: ExecutionTotal = ExecutionTotal(0)
    successful_executions: ExecutionTotal = ExecutionTotal(0)
    success_rate: float | None = None


@dataclass(frozen=True)
class ObservabilityRequest:
    """One observability verb plus everything it needs to run.

    Fields the chosen verb does not read stay at their defaults, so a
    bootstrap and a status write share one shape without either one
    passing arguments the other ignores.
    """

    verb: ObservabilityVerb
    log_path: FilePath | Path | None = None
    verbose: bool = False
    attach_stderr: bool = True
    status: str = ""
    mode: Mode = Mode("")
    headless: HeadlessFlag = HeadlessFlag(False)
    run_id: RunId | str | None = None
    files_processed: int = 0
    files_failed: int = 0
    cpu_sec: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class ObservabilityResponse:
    """What an observability verb produced.

    ``success`` is ``False`` with ``error`` set when the operation could
    not complete, so a bootstrap problem in file-only mode degrades the
    run instead of aborting it. ``report_path`` carries the written
    quality-report path for the report verb.
    """

    success: bool = True
    report_path: FilePath | Path | None = None
    error: str | None = None


__all__ = [
    "ExecutionTotal",
    "MetricsCounters",
    "MetricsSnapshot",
    "ObservabilityRequest",
    "ObservabilityResponse",
    "ObservabilityVerb",
]
