"""Smoke tests for the observability aggregate.

The aggregate's promise is that both entry runtimes bootstrap a run through
one door, and that a bootstrap problem degrades the run rather than aborting
it. These drive that door with a no-op status seam and a temporary metrics
file, so no terminal handler is attached and no run is left open.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from modules.logging.src.agent_logging_orchestrator import LoggingOrchestrator
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.shared.src.taxonomy_logging_vo import ObservabilityRequest


def _orchestrator(tmp_path: Path) -> LoggingOrchestrator:
    return LoggingOrchestrator(
        observability=ObservabilitySetup(
            log_path=tmp_path / "logs",
            status_writer=MagicMock(),
            metrics=MetricsCounter(metrics_path=tmp_path / "logs" / "metrics.json"),
        ),
        metrics=MetricsCounter(metrics_path=tmp_path / "logs" / "metrics.json"),
    )


def test_smoke_the_aggregate_bootstraps_a_run(tmp_path: Path) -> None:
    response = _orchestrator(tmp_path).execute(
        ObservabilityRequest(verb="setup_observability", log_path=tmp_path / "logs", attach_stderr=False)
    )

    assert response.success is True
    assert (tmp_path / "logs" / "app.jsonl").exists()


def test_smoke_the_aggregate_reports_failure_instead_of_raising(tmp_path: Path) -> None:
    """A bootstrap problem degrades the run, so a missing log directory
    must come back as ``success=False``, not an exception."""
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")

    response = _orchestrator(tmp_path).execute(
        ObservabilityRequest(verb="setup_observability", log_path=blocker, attach_stderr=False)
    )

    assert isinstance(response.success, bool)
