"""Acceptance tests for the flush-completeness requirement.

The requirement in `modules/logging/FRD.md` FR-LOGGING-004 is that a close
flushes the run's records before returning, so a crash cannot lose the
final records. These bootstrap the observability stack, bind the run id,
emit records into a per-run log file, detach, and assert every record is on
disk.
"""

from __future__ import annotations

import logging
from pathlib import Path

from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup


def _setup(tmp_path: Path) -> ObservabilitySetup:
    runner = ObservabilitySetup(
        log_path=tmp_path / "logs",
        status_writer=StatusFileWriter(tmp_path / "status.json"),
        metrics=MetricsCounter(metrics_path=tmp_path / "logs" / "metrics.json"),
    )
    runner.setup_observability(log_path=tmp_path / "logs", attach_stderr=False)
    return runner


def test_acceptance_records_written_before_detach_are_flushed(tmp_path: Path) -> None:
    runner = _setup(tmp_path)
    runner.bind_run_context("run-1")
    path = runner.attach_run_log("flush-check", "run-1")
    logging.getLogger().info("first record")
    logging.getLogger().info("second record")
    runner.detach_run_log("run-1")

    content = Path(path).read_text(encoding="utf-8")
    assert "first record" in content
    assert "second record" in content


def test_acceptance_a_detached_run_writes_no_more_records(tmp_path: Path) -> None:
    runner = _setup(tmp_path)
    runner.bind_run_context("run-2")
    path = runner.attach_run_log("detached-check", "run-2")
    runner.detach_run_log("run-2")

    logging.getLogger().info("after detach")
    assert "after detach" not in Path(path).read_text(encoding="utf-8")
