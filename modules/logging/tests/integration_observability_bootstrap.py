"""Integration tests for the observability bootstrap against a real log file.

These bootstrap the full observability stack against a temporary log
directory, so the handler wiring and the JSONL output are exercised rather
than a stub's echo.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup


def _setup(tmp_path: Path) -> ObservabilitySetup:
    log_dir = tmp_path / "logs"
    runner = ObservabilitySetup(
        log_path=log_dir,
        status_writer=StatusFileWriter(tmp_path / "status.json"),
        metrics=MetricsCounter(metrics_path=log_dir / "metrics.json"),
    )
    runner.setup_observability(log_path=log_dir, attach_stderr=False)
    return runner


def test_integration_a_bootstrapped_run_writes_jsonl_to_the_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.jsonl"
    runner = _setup(tmp_path)
    runner.bind_run_context("run-1")

    logging.getLogger().info("an integrated record")
    runner.clear_run_context()

    lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "the bootstrap must create the log file and write records into it"
    assert any("an integrated record" in line for line in lines)
    assert all(json.loads(line) for line in lines), "every line must be a JSON object"


def test_integration_a_status_write_reaches_the_status_file(tmp_path: Path) -> None:
    runner = _setup(tmp_path)

    runner.write_status("running", mode="single", headless=True, run_id="run-1")

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "running"
    assert status["run_id"] == "run-1"
