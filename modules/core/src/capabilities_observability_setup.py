"""Capabilities: observability stack setup (AES403).

Implements IObservabilityProtocol. Metrics counters and status.json writes
live here as helper types (FR-009) — not standalone capabilities.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
import types
from collections.abc import Iterator
from contextlib import nullcontext, suppress
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

sentry_sdk: Any = None
structlog: Any = None
otel_trace: Any = None
OTelResource: Any = None
OTelTracerProvider: Any = None
OTelBatchSpanProcessor: Any = None

with suppress(ImportError):
    import sentry_sdk
with suppress(ImportError):
    import structlog
with suppress(ImportError):
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.resources import Resource as OTelResource
    from opentelemetry.sdk.trace import TracerProvider as OTelTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor as OTelBatchSpanProcessor

from modules.core.src.utility_core_io_writer import atomic_write_json, ensure_dir
from modules.core.src.utility_core_logger_factory import get_logger
from modules.core.src.utility_telemetry_scrubber import (
    harden_private_dir,
    harden_private_file,
    scrub_span_attributes,
    scrub_telemetry_event,
)
from modules.shared.src import utility_core_exit
from modules.shared.src.contract_core_protocol import IMetricsProtocol, IObservabilityProtocol, IStatusProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_JOBS_DIR, DEFAULT_LOG
from modules.shared.src.taxonomy_core_error import ErrorCategory
from modules.shared.src.taxonomy_core_vo import ExitCode, JobName, MessageCount, RunId, ServiceName, StatusRecordVO
from modules.shared.src.utility_core_status import status_path_for

#: Version of the ``status.json`` document contract. Bumped when a field is
#: added or its meaning changes, so external monitors can branch on it
#: (issue #296).
STATUS_SCHEMA_VERSION = 2

# Block 1: Class Definition & Constructor


class MetricsCounter(IMetricsProtocol):
    """Thread-safe metrics collector persisted in a rolling-window JSON file."""

    def __init__(self, metrics_path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._metrics_path = Path(metrics_path or (DEFAULT_LOG / "metrics.json"))
        self._counters: dict[str, int] = {}
        self._execution_events: list[dict[str, Any]] = []
        self._start_time = datetime.now(tz=timezone.utc)
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self._metrics_path.read_text(encoding="utf-8"))
            counters = raw.get("counters", {}) if isinstance(raw, dict) else {}
            if isinstance(counters, dict):
                self._counters = {str(k): int(v) for k, v in counters.items()}
            events = raw.get("execution_events", []) if isinstance(raw, dict) else []
            if isinstance(events, list):
                self._execution_events = [event for event in events if isinstance(event, dict)]
            self._prune_events()
        except (OSError, ValueError, TypeError):
            self._counters = {}
            self._execution_events = []

    def _prune_events(self) -> None:
        cutoff = datetime.now(tz=timezone.utc).timestamp() - 24 * 60 * 60
        kept: list[dict[str, Any]] = []
        for event in self._execution_events:
            try:
                if datetime.fromisoformat(str(event["at"]).replace("Z", "+00:00")).timestamp() >= cutoff:
                    kept.append(event)
            except (KeyError, TypeError, ValueError):
                continue
        self._execution_events = kept

    def _persist(self) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self._prune_events()
        total = len(self._execution_events)
        successful = sum(1 for event in self._execution_events if event.get("success") is True)
        atomic_write_json(
            self._metrics_path,
            {
                "window": "rolling_24h",
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
                "counters": self._counters,
                "execution_events": self._execution_events,
                "total_executions": total,
                "successful_executions": successful,
            },
        )
        harden_private_file(self._metrics_path)

    def increment(self, key: str, amount: MessageCount = MessageCount(1)) -> None:
        """Add *amount* to the counter *key* and persist the metrics file."""
        with self._lock:
            self._counters[key] = self._counters.get(key, MessageCount(0)) + amount
            self._persist()

    def record_execution(self, success: bool) -> None:
        """Record one terminal pipeline execution for the reliability SLO."""
        with self._lock:
            self._execution_events.append({"at": datetime.now(tz=timezone.utc).isoformat(), "success": bool(success)})
            self._persist()

    def record_failure(self, category: str) -> None:
        """Bump one occurrence for *category* in the rolling error counter.

        Unknown category names are ignored so a caller passing a raw exception
        type name cannot inflate the defect counts with unbounded keys; the
        taxonomy is the single source of truth for valid buckets.
        """
        from modules.shared.src.taxonomy_core_error import ErrorCategory

        if category not in ErrorCategory.known():
            return
        with self._lock:
            self._counters[f"error.{category}"] = self._counters.get(f"error.{category}", 0) + 1
            self._persist()

    def failure_counts(self) -> dict[str, int]:
        """Return the rolling per-category error counts, ranked by descending count.

        Keys are ``ErrorCategory`` names with the ``error.`` counter prefix
        stripped, so the QA defect-density report can read them directly.
        """
        with self._lock:
            prefix = "error."
            counts = {key[len(prefix) :]: value for key, value in self._counters.items() if key.startswith(prefix)}
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def get(self, key: str) -> MessageCount:
        """Return the current value of counter *key* (0 when absent)."""
        with self._lock:
            return MessageCount(self._counters.get(key, 0))

    def snapshot(self) -> dict[str, Any]:
        """Return all counters plus rolling-24h execution totals and success rate."""
        with self._lock:
            self._prune_events()
            result: dict[str, Any] = dict(self._counters)
            total = len(self._execution_events)
            successful = sum(1 for event in self._execution_events if event.get("success") is True)
            result["total_executions"] = total
            result["successful_executions"] = successful
            result["success_rate"] = round(successful / total, 6) if total else None
            return result

    def __repr__(self) -> str:
        return f"MetricsCounter(path={self._metrics_path!s})"


class StatusFileWriter(IStatusProtocol):
    """Atomic JSON status file for systemd / monitoring tools."""

    def __init__(self, status_path: Path) -> None:
        self._status_path = status_path
        ensure_dir(self._status_path)

    def write(self, **kwargs: Any) -> None:
        """Atomically write the status JSON from keyword fields.

        When a ``metrics`` mapping is supplied it is embedded under
        ``metrics``, so an external monitor reading ``status.json`` sees the
        same counters the process keeps alive in memory (issue #296). The
        document is also stamped with ``schema_version`` and ``updated_at``
        so a monitor can parse it without guessing. Field contract:

        - ``schema_version``: int, currently 2.
        - ``updated_at``: ISO-8601 UTC timestamp of the write.
        - ``status`` / ``mode`` / ``headless`` / ``run_id``: run identity.
        - ``files_processed`` / ``files_failed`` / ``cpu_sec``: run totals.
        - ``failure_categories``: optional mapping of
          :class:`~modules.shared.src.taxonomy_core_error.ErrorCategory` values
          to occurrence counts, letting monitoring tools answer "which
          capability is most defective?" without parsing ``app.jsonl`` by hand.
        - ``metrics``: counters plus ``total_executions``,
          ``successful_executions``, and ``success_rate`` over a rolling 24 h
          window (``None`` when no execution has been recorded).
        - ``error``: present only when the run failed.
        """
        rec: dict[str, Any] = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": kwargs.get("status", "unknown"),
            "mode": kwargs.get("mode", "unknown"),
            "headless": kwargs.get("headless", False),
            "run_id": kwargs.get("run_id"),
            "files_processed": kwargs.get("files_processed", 0),
            "files_failed": kwargs.get("files_failed", 0),
            "failure_categories": _normalise_categories(kwargs.get("failure_categories")),
        }
        metrics = kwargs.get("metrics")
        if isinstance(metrics, dict):
            rec["metrics"] = metrics
        if kwargs.get("cpu_sec") is not None:
            rec["cpu_sec"] = round(kwargs["cpu_sec"], 2)
        if kwargs.get("error"):
            rec["error"] = kwargs["error"]

        with suppress(OSError):
            atomic_write_json(self._status_path, rec)

    def write_record(self, record: StatusRecordVO, *, metrics: dict[str, Any] | None = None) -> None:
        """Write the status JSON from a typed status record.

        ``metrics`` carries the persisted counter snapshot so a monitor reading
        only ``status.json`` still sees the rolling-24h execution totals
        (issue #296).
        """
        self.write(
            status=record.status,
            mode=record.mode,
            headless=record.headless,
            run_id=record.run_id,
            error=record.error,
            cpu_sec=record.cpu_sec,
            files_processed=record.files_processed,
            files_failed=record.files_failed,
            metrics=metrics,
        )

    def read(self) -> dict[str, Any] | None:
        """Return the parsed status file, or None when missing or invalid."""
        try:
            result: Any = json.loads(self._status_path.read_text(encoding="utf-8"))
            return result if isinstance(result, dict) else None
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return None

    def __repr__(self) -> str:
        return "StatusFileWriter()"

    @classmethod
    def create_default(cls, log_path: Path) -> StatusFileWriter:
        """Build a writer targeting the conventional status path for *log_path*."""
        return cls(status_path_for(log_path))


def get_status_writer(log_path: Path) -> StatusFileWriter:
    """Create a status writer at log_path/status.json."""
    return StatusFileWriter.create_default(log_path)


class ObservabilitySetup(IObservabilityProtocol):
    """Full observability bootstrap: Sentry → OTel → structlog → status → hooks."""

    def __init__(self, log_path: Path, status_writer: IStatusProtocol | None = None) -> None:
        self._log_path = log_path
        self._status_path = status_path_for(log_path)
        self._status_writer = status_writer or StatusFileWriter(self._status_path)
        self._metrics = MetricsCounter(metrics_path=self._log_path / "metrics.json")
        self._run_handlers: dict[str, RotatingFileHandler] = {}
        self._formatter: Any = None

    # ─── Block 2: Public Contract (IObservabilityProtocol ONLY) ──

    @property
    def metrics(self) -> MetricsCounter:
        """Return the persistent execution metrics collector."""
        return self._metrics

    def setup_observability(self, log_path: Path, verbose: bool = False, attach_stderr: bool = True) -> None:
        """Bootstrap observability stack in 4 sequential steps:

        Step 1: Ensure log target directory exists
        Step 2: Configure error tracking (Sentry) & distributed tracing (OpenTelemetry)
        Step 3: Configure structlog/stdlib logging & JSONL file handlers
        Step 4: Install global process excepthooks

        Parameters
        ----------
        attach_stderr:
            When False, skip attaching the ``StreamHandler(sys.stderr)``. This
            is required for the interactive TUI: Playwright browser callbacks
            run on their own threads and emit log records that would otherwise
            be written straight to the terminal, corrupting the TUI canvas.
        """
        # Step 1: Ensure log target directory. Log records carry local paths
        # and run metadata, so the directory is created with owner-only
        # permissions regardless of the process umask (issue #352).
        target_path = log_path or self._log_path
        harden_private_dir(target_path)

        # Step 2: Configure error tracking & tracing
        self._configure_sentry()
        self._configure_tracing()

        # Step 3: Configure structlog/stdlib logging
        self._configure_logging(target_path, verbose=verbose, attach_stderr=attach_stderr)

        # Step 4: Install global process excepthooks
        install_excepthooks()

        # Step 5: Record the effective telemetry mode so a production host that
        # silently lost error tracking says so in the log at startup (#297).
        mode = effective_telemetry_mode()
        if mode == "file_only":
            log.warning(
                "observability_mode mode=%s environment=%s detail=no Sentry DSN and no OTLP endpoint; "
                "failures reach the file log only",
                mode,
                os.getenv("ENVIRONMENT", "production"),
            )
        else:
            log.info(
                "observability_mode mode=%s environment=%s",
                mode,
                os.getenv("ENVIRONMENT", "production"),
            )

    def _configure_sentry(self) -> None:
        """Configure Sentry and log an explicit degraded event when it is off.

        Security (issue #352): the ``before_send`` hook redacts host paths and
        prompt-derived fields so no local data leaves the host unless an
        operator explicitly opted in with ``SENTRY_DSN``. An empty DSN is a
        hard no-op.

        Missing DSN or missing ``sentry_sdk`` is a no-op by design for local
        development. On a production host it means errors are only in file
        logs, so an operator-visible event names exactly what is off
        (issue #297).
        """
        environment = os.getenv("ENVIRONMENT", "production")
        if sentry_sdk is None:
            log.info(
                "observability_degraded reason=%s environment=%s",
                "sentry_sdk not installed",
                environment,
            )
            return
        dsn = os.getenv("SENTRY_DSN", "")
        if not dsn:
            log.info(
                "observability_degraded reason=%s environment=%s hint=%s",
                "SENTRY_DSN empty — error tracking is off",
                environment,
                "Set SENTRY_DSN or set ENVIRONMENT=development to silence this warning"
                if environment != "development"
                else "development mode is expected to run without Sentry",
            )
            return
        with suppress(Exception):
            sentry_sdk.init(
                dsn=dsn,
                environment=environment,
                traces_sample_rate=1.0,
                before_send=scrub_telemetry_event,
            )
        log.info("sentry_ready environment=%s", environment)

    def _configure_tracing(self) -> None:
        """Configure OpenTelemetry tracing with span-attribute scrubbing.

        Security (issue #352): OTLP egress is opt-in; when an endpoint is set,
        span attributes are scrubbed so local home paths never leave the host.
        Logs a degraded event when tracing is off (issue #297).
        """
        environment = os.getenv("ENVIRONMENT", "production")
        if otel_trace is None or OTelResource is None or OTelTracerProvider is None:
            log.info(
                "observability_degraded reason=%s environment=%s",
                "OpenTelemetry not installed — tracing is off",
                environment,
            )
            return
        try:
            resource = OTelResource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", ServiceName("qwen-web"))})
            provider = OTelTracerProvider(resource=resource)
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
            otlp_exporter: Any = None
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                if endpoint and OTelBatchSpanProcessor is not None:
                    otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
                    provider.add_span_processor(OTelBatchSpanProcessor(_make_scrubbed_exporter(otlp_exporter)))
            except ImportError:
                pass
            otel_trace.set_tracer_provider(provider)
            if endpoint:
                log.info("tracing_ready environment=%s exporter=otlp", environment)
            else:
                log.info(
                    "observability_degraded reason=%s environment=%s",
                    "OTEL_EXPORTER_OTLP_ENDPOINT empty — traces are collected in-process only",
                    environment,
                )
        except (ImportError, RuntimeError):
            log.info("observability_degraded reason=%s environment=%s", "OTel init failed", environment)

    def _configure_logging(self, log_path: Path, verbose: bool = False, attach_stderr: bool = True) -> None:
        """Configure structlog/stdlib logging (private helper)."""
        log_level = logging.DEBUG if verbose else logging.INFO
        if structlog is None:
            # Fallback: wire a stdlib JSON formatter + file handler so per-run
            # logs still work when structlog is not installed.
            self._formatter = _make_json_formatter()
            root = logging.getLogger()
            root.setLevel(log_level)
            if attach_stderr:
                stderr_handler = logging.StreamHandler(sys.stderr)
                stderr_handler.setFormatter(self._formatter)
                root.addHandler(stderr_handler)
            try:
                file_handler = RotatingFileHandler(
                    log_path / "app.jsonl", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
                )
                file_handler.setFormatter(self._formatter)
                root.addHandler(file_handler)
                harden_private_file(log_path / "app.jsonl")
            except OSError:
                pass
            return

        shared_processors: list[Any] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_trace_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        is_dev = os.getenv("ENVIRONMENT", "production") == "development" or sys.stderr.isatty()
        renderer = (
            structlog.dev.ConsoleRenderer(colors=True)
            if is_dev
            else structlog.processors.JSONRenderer(ensure_ascii=False)
        )

        structlog.configure(
            processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
        self._formatter = formatter

        root = logging.getLogger()
        root.setLevel(logging.DEBUG if verbose else logging.INFO)
        for handler in list(root.handlers):
            if handler.__class__.__name__.endswith("LogHandler"):
                continue
            root.removeHandler(handler)
        if attach_stderr:
            stderr_handler = logging.StreamHandler(sys.stderr)
            stderr_handler.setFormatter(formatter)
            root.addHandler(stderr_handler)
        try:
            file_handler = RotatingFileHandler(
                log_path / "app.jsonl", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            harden_private_file(log_path / "app.jsonl")
        except OSError:
            pass

    def get_logger(self, name: str = "qwen-web") -> Any:
        """Return a bound structlog logger."""
        return _get_logger(name)

    def get_tracer(self) -> Any:
        """Return the OpenTelemetry tracer (no-op when OTel is absent)."""
        return _get_tracer()

    def start_span(self, name: str) -> Any:
        """Start and return a tracing span named *name*."""
        return _start_span(name)

    def bind_run_context(self, run_id: str, **extra: Any) -> None:
        """Bind *run_id* and extras to the logging context for this run."""
        _bind_run_context(run_id, **extra)

    def clear_run_context(self) -> None:
        """Clear the run-scoped logging context."""
        _clear_run_context()

    def attach_run_log(self, job_name: JobName, run_id: RunId) -> Path:
        """Attach a per-run JSONL log file under the jobs directory.

        Every log record emitted while this handler is attached is written to
        ``{DEFAULT_JOBS_DIR}/{job_name}_{timestamp}_{run_id}.jsonl`` in
        addition to the aggregate ``app.jsonl``. Use ``detach_run_log`` to
        close the handler once the run finishes.
        """
        jobs_dir = DEFAULT_JOBS_DIR
        try:
            # Per-run JSONL artifacts carry local paths and run metadata, so the
            # jobs directory and every file in it are owner-only (issue #352).
            harden_private_dir(jobs_dir)
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", job_name).strip("._") or "run"
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = jobs_dir / f"{safe_name}_{ts}_{run_id}.jsonl"
            if self._formatter is not None:
                handler = RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=2, encoding="utf-8")
                handler.setFormatter(self._formatter)
                harden_private_file(path)
                # Keep only records whose bound run_id matches this run so
                # overlapping runs never leak records into each other's log.
                handler.addFilter(_make_run_id_filter(str(run_id)))
                logging.getLogger().addHandler(handler)
                self._run_handlers[str(run_id)] = handler
            return path
        except OSError:
            return jobs_dir / f"{run_id}.jsonl"

    def detach_run_log(self, run_id: RunId) -> None:
        """Detach and close the per-run log handler for the given run id."""
        handler = self._run_handlers.pop(str(run_id), None)
        if handler is not None:
            logging.getLogger().removeHandler(handler)
            with suppress(Exception):
                handler.close()

    def exit_code_for(self, exc: BaseException) -> ExitCode:
        """Map an exception to the process exit code contract."""
        return ExitCode(utility_core_exit.exit_code_for(exc))

    def write_status(
        self,
        status: str,
        mode: str,
        headless: bool,
        run_id: str | None = None,
        *,
        files_processed: int = 0,
        files_failed: int = 0,
        cpu_sec: float | None = None,
        error: str | None = None,
    ) -> None:
        """Write status.json, persisting the live metrics snapshot alongside the run.

        Including :py:meth:`MetricsCounter.snapshot` in every write means
        external monitors reading ``status.json`` see the rolling-window
        execution counters without needing to scrape ``metrics.json``
        separately (issue #296).
        """
        self._status_writer.write(
            status=status,
            mode=mode,
            headless=headless,
            run_id=run_id,
            files_processed=files_processed,
            files_failed=files_failed,
            cpu_sec=cpu_sec,
            error=error,
            metrics=self._metrics.snapshot(),
        )

    def install_excepthooks(self) -> None:
        """Install global exception handlers (delegates to module-level function)."""
        install_excepthooks()

    def write_quality_report(self, *, run_id: str | None = None) -> Path:
        """Produce ``quality_report.json`` with error distribution and defect density.

        Reads ``app.jsonl`` under ``self._log_path``, extracts every record
        whose ``level`` is ``error`` or ``critical``, counts them per
        :class:`~modules.shared.src.taxonomy_core_error.ErrorCategory`, and
        folds the rolling-24h metrics snapshot into the report so a monitoring
        dashboard can answer "which capability is most defective?" from one
        JSON object instead of parsing JSONL by hand.
        """
        distribution: dict[str, int] = {}
        error_records = 0
        for payload in self._iter_error_records():
            error_records += 1
            category = _category_from_record(payload)
            distribution[category] = distribution.get(category, 0) + 1

        executions: dict[str, Any] = self._metrics.snapshot()
        total = int(executions.get("total_executions", 0) or 0)
        report: dict[str, Any] = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "run_id": run_id,
            "source_log": str(self._log_path / "app.jsonl"),
            "error_records": error_records,
            "error_distribution": dict(sorted(distribution.items(), key=lambda kv: (-kv[1], kv[0]))),
            "defect_density": round(error_records / total, 6) if total else None,
            "executions": executions,
        }
        quality_path = self._log_path / "quality_report.json"
        atomic_write_json(quality_path, report)
        return quality_path

    def _iter_error_records(self) -> Iterator[dict[str, Any]]:
        """Yield every ``error``/``critical`` record parsed from ``app.jsonl``.

        Blank lines, unparseable JSON, and non-object records are skipped so a
        truncated final line — the normal result of a SIGKILL mid-write — never
        corrupts the report.
        """
        log_path = self._log_path / "app.jsonl"
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except (ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("level", "")).lower() in ("error", "critical"):
                yield payload

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of ObservabilitySetup."""
        return f"ObservabilitySetup(log_path={self._log_path!r})"


# ─── Module-level helper functions ──────────────────────────────────────────


def _normalise_categories(raw: Any) -> dict[str, int]:
    """Coerce a failure-category breakdown into a sorted ``{category: count}`` map.

    Accepts ``None``, a mapping, or an iterable of pairs.  Non-integer counts
    are dropped rather than written as strings, so ``status.json`` keeps a
    stable schema that monitoring tools can sum without type coercion.
    """
    if not raw:
        return {}
    items = raw.items() if isinstance(raw, dict) else raw
    result: dict[str, int] = {}
    for pair in items:
        try:
            key, value = pair
            result[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return dict(sorted(result.items(), key=lambda kv: (-kv[1], kv[0])))


def _category_from_record(payload: dict[str, Any]) -> str:
    """Return the error category for one log record.

    Prefers an explicit ``category`` field written by the caller; falls back to
    ``other`` so an uncategorized error still counts toward defect density
    rather than silently disappearing from the distribution.
    """
    from modules.shared.src.taxonomy_core_error import ErrorCategory

    raw = payload.get("category")
    if isinstance(raw, str) and raw in ErrorCategory.known():
        return raw
    return "other"


def _get_logger(name: str = "qwen-web") -> Any:
    """Return a structlog bound logger, falling back to stdlib logging."""
    if structlog is not None:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def _get_tracer(name: str = "qwen-web") -> Any:
    """Return an OpenTelemetry tracer, or None when tracing unavailable."""
    if otel_trace is not None:
        return otel_trace.get_tracer(name)
    return None


def _start_span(name: str) -> Any:
    """Context manager for an OTel span; yields nullcontext (no-op) when tracing unavailable."""
    tracer = _get_tracer()
    if tracer is None:
        return nullcontext()
    return tracer.start_as_current_span(name)


def effective_telemetry_mode() -> str:
    """Return the effective telemetry mode: ``full``, ``sentry``, ``otlp``, or ``file_only``.

    ``file_only`` means neither Sentry nor OTLP export is configured, so
    failures reach only the rotating file log (issue #297). Callers use this
    to warn an operator that a production host is running without external
    error tracking.
    """
    has_sentry = sentry_sdk is not None and bool(os.getenv("SENTRY_DSN", "").strip())
    has_otlp = bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip())
    if has_sentry and has_otlp:
        return "full"
    if has_sentry:
        return "sentry"
    if has_otlp:
        return "otlp"
    return "file_only"


def _json_format(record: logging.LogRecord) -> str:
    """Render a stdlib LogRecord as a single JSON line (structlog-free)."""
    payload: dict[str, Any] = {
        "event": record.getMessage(),
        "level": record.levelname.lower(),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "logger": record.name,
    }
    if record.exc_info:
        payload["exc_info"] = logging.Formatter().formatException(record.exc_info)
    return json.dumps(payload, ensure_ascii=False)


def _make_json_formatter() -> Any:
    """Return a JSON-lines formatter-compatible object (no class definitions)."""
    return types.SimpleNamespace(format=_json_format)


def _make_run_id_filter(run_id: str) -> Any:
    """Return a filter that keeps only records bound to ``run_id``.

    Reads the structlog contextvars in the emitting thread so that concurrent
    runs (TUI slots, MCP background jobs) never cross-write per-run logs.
    """

    def _filter(_record: logging.LogRecord) -> bool:
        if structlog is None:
            return True
        try:
            ctx = structlog.contextvars.get_contextvars()
        except Exception:
            return False
        return str(ctx.get("run_id", "")) == run_id

    return types.SimpleNamespace(filter=_filter)


def add_trace_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inject active OTel trace_id/span_id into every log event."""
    if otel_trace is None:
        return event_dict
    span = otel_trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
        event_dict["trace_sampled"] = ctx.trace_flags.sampled
    return event_dict


def _bind_run_context(run_id: str, **extra: Any) -> None:
    """Bind run-scoped fields into structlog contextvars."""
    if structlog is not None:
        structlog.contextvars.bind_contextvars(run_id=run_id, **extra)


def _clear_run_context() -> None:
    """Clear all run-scoped contextvars."""
    if structlog is not None:
        structlog.contextvars.clear_contextvars()


def _excepthook(exc_type: type[BaseException], exc_value: BaseException, _exc_tb: Any) -> None:
    logger = _get_logger("qwen-web")
    if issubclass(exc_type, KeyboardInterrupt):
        logger.warning("interrupted")
        sys.exit(130)
    _report_critical(logger, exc_value, "unhandled_exception")
    sys.exit(1)


def _thread_excepthook(args: Any) -> None:
    logger = _get_logger("qwen-web")
    _report_critical(logger, args.exc_value, "unhandled_exception_in_thread")


# ─── Security audit channel (issue #354) ───────────────────────────────────
# Authentication failures and CAPTCHA challenges are security signals: they can
# indicate a session-hijack attempt, account lockout, or automation abuse. The
# audit logger records every event on the ``security.audit`` channel so an
# operator aggregating ``app.jsonl`` can distinguish a single cookie-expiry
# from a burst of bot challenges. The rolling-window counter lets SIEM tools
# alert on repeated challenges without a second state store.

_security_audit_logger = _get_logger("security.audit")

# A window longer than this makes the counter useless for live incident
# response; shorter windows would need more state than the process can justify.
_AUTH_FAILURE_WINDOW_SEC = 60.0
_ALERT_THRESHOLD = 5
_auth_failure_events: list[tuple[float, str]] = []
_auth_failure_lock = threading.Lock()


def _record_auth_failure(event_category: str) -> None:
    """Record one auth/challenge failure and log it on the security.audit channel.

    The event is emitted at warning level so it is visible in default logging
    configuration; the structured fields (``event_name``, ``event_category``,
    ``recent_failures``) are what SIEM ingestion keys on. Sustained failures
    escalate to ``security_alert`` at error level.
    """
    now = time.time()
    with _auth_failure_lock:
        # Prune events outside the window so the counter stays bounded.
        _auth_failure_events[:] = [(ts, cat) for ts, cat in _auth_failure_events if now - ts < _AUTH_FAILURE_WINDOW_SEC]
        _auth_failure_events.append((now, event_category))
        recent_count = len(_auth_failure_events)

    _security_audit_logger.warning(
        "auth_or_challenge_failure",
        event_name="security.audit",
        event_category=event_category,
        recent_failures=recent_count,
    )
    if recent_count >= _ALERT_THRESHOLD:
        _security_audit_logger.error(
            "security_alert",
            event_name="security.audit",
            alert="auth_failure_threshold_exceeded",
            threshold=_ALERT_THRESHOLD,
            recent_failures=recent_count,
            window_sec=_AUTH_FAILURE_WINDOW_SEC,
        )


def auth_failure_count(window_sec: float = _AUTH_FAILURE_WINDOW_SEC) -> int:
    """Return the number of auth/challenge failures recorded in *window_sec*.

    Exposed so ``MetricsCounter.snapshot()`` or a custom exporter can surface
    the same value as a metric without duplicating the counter state.
    """
    with _auth_failure_lock:
        now = time.time()
        cutoff = now - window_sec
        return sum(1 for ts, _cat in _auth_failure_events if ts >= cutoff)


def _report_critical(logger: Any, exc_value: BaseException, event_name: str) -> None:
    """Log a critical exception and attempt Sentry capture.

    Security (issue #354): auth-class exceptions are additionally routed to
    the ``security.audit`` channel so operators can track repeated challenges.
    """
    category = ErrorCategory.categorize(exc_value)
    if category in ("auth", "rate_limit"):
        _record_auth_failure(category)
    logger.critical(
        event_name,
        exc_info=(type(exc_value), exc_value, exc_value.__traceback__),
        exc_type=type(exc_value).__name__,
        category=category,
    )
    if sentry_sdk is not None:
        sentry_sdk.capture_exception(exc_value)


# ─── OTel span scrubber (issue #352) ────────────────────────────────────────


def _make_scrubbed_exporter(exporter: Any) -> Any:
    """Wrap an OTel span exporter so every batch has host paths scrubbed first.

    The wrapper implements ``export(spans, ...)`` with the same signature,
    scrubbing each span's attributes in place before delegating to the
    original exporter. This keeps scrubbing transparent to all span
    producers without requiring changes at each call site.
    """

    def _scrub_spans(spans: Any) -> None:
        for span in spans:
            attrs = getattr(span, "attributes", None)
            if attrs:
                scrubbed = scrub_span_attributes(dict(attrs))
                for key in list(attrs.keys()):
                    attrs.pop(key)
                attrs.update(scrubbed)

    def export(spans: Any, *args: Any, **kwargs: Any) -> Any:
        _scrub_spans(spans)
        return exporter.export(spans, *args, **kwargs)

    def shutdown(*args: Any, **kwargs: Any) -> None:
        with suppress(Exception):
            exporter.shutdown(*args, **kwargs)

    def force_flush(*args: Any, **kwargs: Any) -> Any:
        with suppress(Exception):
            return exporter.force_flush(*args, **kwargs)

    # BatchSpanProcessor expects an ExportSpan with .export/.shutdown/.force_flush
    return types.SimpleNamespace(export=export, shutdown=shutdown, force_flush=force_flush)


def install_excepthooks() -> None:
    """Install global exception handlers so crashes are logged as structured events."""
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


__all__ = [
    "auth_failure_count",
    "get_status_writer",
    "MetricsCounter",
    "ObservabilitySetup",
    "StatusFileWriter",
    "install_excepthooks",
]

log = get_logger("capabilities_observability")
