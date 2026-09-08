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
import types
from contextlib import nullcontext, suppress
from datetime import datetime, timezone
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
from modules.shared.src import utility_core_exit
from modules.shared.src.contract_core_protocol import IMetricsProtocol, IObservabilityProtocol, IStatusProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_JOBS_DIR
from modules.shared.src.taxonomy_core_error import ErrorCategory
from modules.shared.src.taxonomy_core_vo import ExitCode, JobName, MessageCount, RunId, ServiceName, StatusRecordVO
from modules.shared.src.utility_core_status import status_path_for

# Block 1: Class Definition & Constructor


class MetricsCounter(IMetricsProtocol):
    """Thread-safe in-memory metrics collector (not persisted across restarts)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._start_time = datetime.now(tz=timezone.utc)

    def increment(self, key: str, amount: MessageCount = MessageCount(1)) -> None:
        with self._lock:
            self._counters[key] = self._counters.get(key, MessageCount(0)) + amount

    def get(self, key: str) -> MessageCount:
        with self._lock:
            return MessageCount(self._counters.get(key, 0))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._counters)

    def __repr__(self) -> str:
        return "MetricsCounter()"


class StatusFileWriter(IStatusProtocol):
    """Atomic JSON status file for systemd / monitoring tools."""

    def __init__(self, status_path: Path) -> None:
        self._status_path = status_path
        ensure_dir(self._status_path)

    def write(self, **kwargs: Any) -> None:
        rec: dict[str, Any] = {
            "status": kwargs.get("status", "unknown"),
            "mode": kwargs.get("mode", "unknown"),
            "headless": kwargs.get("headless", False),
            "run_id": kwargs.get("run_id"),
            "files_processed": kwargs.get("files_processed", 0),
            "files_failed": kwargs.get("files_failed", 0),
        }
        if kwargs.get("cpu_sec") is not None:
            rec["cpu_sec"] = round(kwargs["cpu_sec"], 2)
        if kwargs.get("error"):
            rec["error"] = kwargs["error"]

        with suppress(OSError):
            atomic_write_json(self._status_path, rec)

    def write_record(self, record: StatusRecordVO) -> None:
        self.write(
            status=record.status,
            mode=record.mode,
            headless=record.headless,
            run_id=record.run_id,
            error=record.error,
            cpu_sec=record.cpu_sec,
            files_processed=record.files_processed,
            files_failed=record.files_failed,
        )

    def read(self) -> dict[str, Any] | None:
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
        self._metrics = MetricsCounter()
        self._run_handlers: dict[str, logging.FileHandler] = {}
        self._formatter: Any = None

    # ─── Block 2: Public Contract (IObservabilityProtocol ONLY) ──

    def setup_observability(self, log_path: Path | None = None, verbose: bool = False) -> None:
        """Bootstrap observability stack in 4 sequential steps:

        Step 1: Ensure log target directory exists
        Step 2: Configure error tracking (Sentry) & distributed tracing (OpenTelemetry)
        Step 3: Configure structlog/stdlib logging & JSONL file handlers
        Step 4: Install global process excepthooks
        """
        # Step 1: Ensure log target directory
        target_path = log_path or self._log_path
        target_path.mkdir(parents=True, exist_ok=True)

        # Step 2: Configure error tracking & tracing
        self._configure_sentry()
        self._configure_tracing()

        # Step 3: Configure structlog/stdlib logging
        self._configure_logging(target_path, verbose=verbose)

        # Step 4: Install global process excepthooks
        install_excepthooks()

    def _configure_sentry(self) -> None:
        """Configure Sentry (private helper)."""
        if sentry_sdk is None:
            return
        dsn = os.getenv("SENTRY_DSN", "")
        if not dsn:
            return
        with suppress(Exception):
            sentry_sdk.init(
                dsn=dsn,
                environment=os.getenv("ENVIRONMENT", "production"),
                traces_sample_rate=1.0,
            )

    def _configure_tracing(self) -> None:
        """Configure OpenTelemetry tracing (private helper)."""
        if otel_trace is None or OTelResource is None or OTelTracerProvider is None:
            return
        try:
            resource = OTelResource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", ServiceName("qwen-web"))})
            provider = OTelTracerProvider(resource=resource)
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                if endpoint and OTelBatchSpanProcessor is not None:
                    provider.add_span_processor(OTelBatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            except ImportError:
                pass
            otel_trace.set_tracer_provider(provider)
        except (ImportError, RuntimeError):
            pass

    def _configure_logging(self, log_path: Path, verbose: bool = False) -> None:
        """Configure structlog/stdlib logging (private helper)."""
        log_level = logging.DEBUG if verbose else logging.INFO
        if structlog is None:
            # Fallback: wire a stdlib JSON formatter + file handler so per-run
            # logs still work when structlog is not installed.
            self._formatter = _make_json_formatter()
            root = logging.getLogger()
            root.setLevel(log_level)
            stderr_handler = logging.StreamHandler(sys.stderr)
            stderr_handler.setFormatter(self._formatter)
            root.addHandler(stderr_handler)
            try:
                file_handler = logging.FileHandler(log_path / "app.jsonl", encoding="utf-8")
                file_handler.setFormatter(self._formatter)
                root.addHandler(file_handler)
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
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(formatter)
        root.addHandler(stderr_handler)
        try:
            file_handler = logging.FileHandler(log_path / "app.jsonl", encoding="utf-8")
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            pass

    def get_logger(self, name: str = "qwen-web") -> Any:
        return _get_logger(name)

    def get_tracer(self) -> Any:
        return _get_tracer()

    def start_span(self, name: str) -> Any:
        return _start_span(name)

    def bind_run_context(self, run_id: str, **extra: Any) -> None:
        _bind_run_context(run_id, **extra)

    def clear_run_context(self) -> None:
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
            jobs_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", job_name).strip("._") or "run"
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = jobs_dir / f"{safe_name}_{ts}_{run_id}.jsonl"
            if self._formatter is not None:
                handler = logging.FileHandler(path, encoding="utf-8")
                handler.setFormatter(self._formatter)
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
        return ExitCode(utility_core_exit.exit_code_for(exc))

    def write_status(self, status: str, mode: str, headless: bool, run_id: str | None = None) -> None:
        """Write status.json via the owned (or injected) status writer."""
        self._status_writer.write(status=status, mode=mode, headless=headless, run_id=run_id)

    def install_excepthooks(self) -> None:
        """Install global exception handlers (delegates to module-level function)."""
        install_excepthooks()

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of ObservabilitySetup."""
        return f"ObservabilitySetup(log_path={self._log_path!r})"


# ─── Module-level helper functions ──────────────────────────────────────────


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


def _report_critical(logger: Any, exc_value: BaseException, event_name: str) -> None:
    """Log a critical exception and attempt Sentry capture."""
    logger.critical(
        event_name,
        exc_info=(type(exc_value), exc_value, exc_value.__traceback__),
        exc_type=type(exc_value).__name__,
        category=ErrorCategory.categorize(exc_value),
    )
    if sentry_sdk is not None:
        sentry_sdk.capture_exception(exc_value)


def install_excepthooks() -> None:
    """Install global exception handlers so crashes are logged as structured events."""
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


log = get_logger("capabilities_observability")
