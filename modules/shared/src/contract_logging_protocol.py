"""Logging-domain capability contracts (AES102 `_protocol`).

One file for the logging feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IObservabilityProtocol`` → ``ObservabilitySetup`` (bootstrap, spans, run logs, hooks)
- ``IMetricsProtocol``      → ``MetricsCounter``      (in-memory counters, failure tally)

The status-file seam ``IStatusProtocol`` belongs to the jobs feature,
whose ``StatusFileWriter`` implements it; it lives in
``contract_jobs_protocol.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from modules.shared.src.taxonomy_core_event import EventMessage
from modules.shared.src.taxonomy_core_vo import (
    ExitCode,
    FailureCategory,
    FailureCategoryCounts,
    JobName,
    LoggerName,
    MessageCount,
    MetricsSnapshot,
    RunId,
)


class IObservabilityProtocol(ABC):
    """Observability capability contract (logging, tracing, hooks)."""

    @abstractmethod
    def setup_observability(self, log_path: Path, verbose: bool = False, attach_stderr: bool = True) -> None:
        """Bootstrap Sentry/OTel/structlog + global hooks.

        ``attach_stderr`` False skips the stderr stream handler, which the
        interactive TUI needs so browser-callback logs do not corrupt the
        terminal canvas.
        """
        ...

    @abstractmethod
    def get_logger(self, name: LoggerName = LoggerName("qwen-web")) -> Any:
        """Return a bound logger."""
        ...

    @abstractmethod
    def start_span(self, name: LoggerName) -> Any:
        """Return a span context manager (or no-op)."""
        ...

    @abstractmethod
    def bind_run_context(self, run_id: RunId, **extra: Any) -> None:
        """Bind run-scoped contextvars, carrying *extra* as the binding values."""
        ...

    @abstractmethod
    def clear_run_context(self) -> None:
        """Clear run-scoped contextvars."""
        ...

    @abstractmethod
    def attach_run_log(self, job_name: JobName, run_id: RunId) -> Path:
        """Attach a per-run JSONL log file under the jobs directory.

        ``run_id`` is the file suffix and correlation key.
        """
        ...

    @abstractmethod
    def detach_run_log(self, run_id: RunId) -> None:
        """Detach and close the per-run log handler for the given run id."""
        ...

    @abstractmethod
    def exit_code_for(self, exc: BaseException) -> ExitCode:
        """Map an unhandled exception to a process exit code."""
        ...

    @abstractmethod
    def install_excepthooks(self) -> None:
        """Install global exception handlers."""
        ...

    @abstractmethod
    def write_status(
        self,
        status: str,
        mode: str,
        headless: bool,
        run_id: RunId | None = None,
        *,
        files_processed: int = 0,
        files_failed: int = 0,
        cpu_sec: float | None = None,
        error: str | None = None,
    ) -> None:
        """Write status.json, persisting the live metrics snapshot alongside the run.

        Including the metrics snapshot in every write means external monitors
        reading ``status.json`` see the rolling-window execution counters
        without scraping ``metrics.json`` separately.
        """
        ...

    @abstractmethod
    def write_quality_report(self, *, run_id: RunId | None = None) -> Path:
        """Aggregate the error-category distribution of ``app.jsonl`` and persist it.

        The report answers "which capability is most defective?" without a
        human reading the JSONL log: failures are bucketed by
        :class:`~modules.shared.src.taxonomy_core_error.ErrorCategory` and
        ranked by count, alongside the rolling-24h execution totals.
        """
        ...


class IMetricsProtocol(ABC):
    """In-memory metrics collection capability contract."""

    @abstractmethod
    def increment(self, key: EventMessage, amount: MessageCount = MessageCount(1)) -> None:
        """Increment a counter by the given amount."""
        ...

    @abstractmethod
    def get(self, key: EventMessage) -> MessageCount:
        """Return the current value of a counter."""
        ...

    @abstractmethod
    def snapshot(self) -> MetricsSnapshot:
        """Return a shallow copy of all counters."""
        ...

    @abstractmethod
    def record_execution(self, success: bool) -> None:
        """Record a completed pipeline run for the rolling-window execution log."""
        ...

    @abstractmethod
    def record_failure(self, category: FailureCategory) -> None:
        """Record a failed run under *category* for the failure tally."""
        ...

    @abstractmethod
    def failure_counts(self) -> FailureCategoryCounts:
        """Return the per-category failure tally."""
        ...


__all__ = [
    "IObservabilityProtocol",
    "IMetricsProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IObservabilityProtocol": IObservabilityProtocol,
    "IMetricsProtocol": IMetricsProtocol,
}
