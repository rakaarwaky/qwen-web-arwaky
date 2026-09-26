"""Agent: run the observability bootstrap, status file, and quality report.

``root_cli_main_entry`` and ``root_mcp_main_entry`` used to call
``setup_observability`` straight on the capability, which meant the
argument each entry had to supply — and the one each entry could forget —
was spread over two files. This orchestrator owns the verb routing so both
entries call one method and the argument contract lives in one place.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.contract_logging_aggregate import IObservabilityAggregate
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.taxonomy_core_error import QwenCliError
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    ObservabilityRequest,
    ObservabilityResponse,
    RunId,
)

__all__ = ["LoggingOrchestrator"]


class LoggingOrchestrator(IObservabilityAggregate):
    """Route observability verbs to the logging capability."""

    def __init__(self, observability: IObservabilityProtocol) -> None:
        """Wrap the observability capability.

        The dependency arrives as ``IObservabilityProtocol`` so a test can
        inject a stub that never opens a log file or contacts Sentry.
        """
        self._observability = observability

    def execute(self, request: ObservabilityRequest) -> ObservabilityResponse:
        """Route the observability verb to its operation and report the outcome.

        A failing verb returns ``success=False`` with the reason rather than
        raising, so a bootstrap problem in file-only mode degrades the run
        instead of aborting it.
        """
        try:
            if request.verb == "setup_observability":
                self._observability.setup_observability(
                    log_path=self._log_path(request),
                    verbose=request.verbose,
                    attach_stderr=request.attach_stderr,
                )
                return ObservabilityResponse(success=True)
            if request.verb == "write_status":
                self._observability.write_status(
                    status=request.status or "",
                    mode=request.mode or "",
                    headless=request.headless,
                    run_id=RunId(request.run_id) if request.run_id else None,
                    files_processed=request.files_processed,
                    files_failed=request.files_failed,
                    cpu_sec=request.cpu_sec,
                    error=request.error,
                )
                return ObservabilityResponse(success=True)
            if request.verb == "write_quality_report":
                report = self._observability.write_quality_report(
                    run_id=RunId(request.run_id) if request.run_id else None
                )
                return ObservabilityResponse(success=True, report_path=FilePath(report))
        except Exception as exc:
            return ObservabilityResponse(success=False, error=str(exc))
        raise QwenCliError(f"Unknown observability verb: {request.verb!r}")  # pragma: no cover

    def _log_path(self, request: ObservabilityRequest) -> Path:
        """Return the log path the bootstrap verb writes to.

        A request with no path falls back to the shared default so a caller
        that only sets the verb still gets a real log file.
        """
        from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG

        return Path(request.log_path) if request.log_path is not None else Path(DEFAULT_LOG)
