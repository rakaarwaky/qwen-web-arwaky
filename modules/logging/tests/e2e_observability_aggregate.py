"""End-to-end tests for the observability aggregate over the full verb cycle.

These drive ``LoggingOrchestrator`` with the real bootstrap capability, the
real status writer, and the real metrics counter against a temporary log
directory, so the setup-then-write-status-then-report cycle a caller runs
is exercised end to end without a browser or a network.
"""

from __future__ import annotations

import json
from pathlib import Path

from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.logging.src.agent_logging_orchestrator import LoggingOrchestrator
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.shared.src.taxonomy_logging_vo import ObservabilityRequest, ObservabilityResponse


def _orchestrator(tmp_path: Path) -> LoggingOrchestrator:
    log_dir = tmp_path / "logs"
    setup = ObservabilitySetup(
        log_path=log_dir,
        status_writer=StatusFileWriter(tmp_path / "status.json"),
        metrics=MetricsCounter(metrics_path=log_dir / "metrics.json"),
    )
    setup.setup_observability(log_path=log_dir, attach_stderr=False)
    return LoggingOrchestrator(observability=setup, metrics=setup.metrics)


def test_e2e_setup_then_status_then_report_flow(tmp_path: Path) -> None:
    """The full verb cycle: setup, a status write, and a quality report."""
    orchestrator = _orchestrator(tmp_path)

    status = orchestrator.execute(
        ObservabilityRequest(verb="write_status", status="running", mode="single", run_id="run-1")
    )
    assert isinstance(status, ObservabilityResponse)
    assert status.success
    on_disk = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert on_disk["status"] == "running"
    assert on_disk["run_id"] == "run-1"

    report = orchestrator.execute(ObservabilityRequest(verb="write_quality_report", run_id="run-1"))
    assert isinstance(report, ObservabilityResponse)
    assert report.success
    assert report.report_path is not None
    assert report.report_path.exists()


def test_e2e_unknown_verb_fails_closed_with_a_named_error(tmp_path: Path) -> None:
    """A verb the aggregate does not route is rejected without a response."""
    import pytest

    from modules.shared.src.taxonomy_core_error import QwenCliError

    orchestrator = _orchestrator(tmp_path)

    with pytest.raises(QwenCliError, match="no_such_verb"):
        orchestrator.execute(ObservabilityRequest(verb="no_such_verb"))
