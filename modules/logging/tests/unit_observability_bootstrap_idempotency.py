"""Regression: a bootstrap run twice with one run id attaches no duplicate handler.

FR-LOGGING-001 edge case (modules/logging/FRD.md): ``setup_observability`` is
called by both entry runtimes' orchestrator verbs, and a run id may bootstrap
more than once (retries, MCP tool invocations sharing one setup object). The
second call must not stack a second file or stderr handler on the root
logger: records would then be written twice per run, and ``detach_run_log``
would only remove the first one.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.logging.src.capabilities_metrics_counter import MetricsCounter
from modules.logging.src.capabilities_observability_setup import ObservabilitySetup
from modules.shared.src.common.utility_core_status import status_path_for


@pytest.fixture
def isolated_root_logger():
    """Snapshot and restore the root logger's handlers and level."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        yield root
    finally:
        for h in list(root.handlers):
            if h not in saved_handlers:
                root.removeHandler(h)
        for h in saved_handlers:
            if h not in root.handlers:
                root.addHandler(h)
        root.setLevel(saved_level)


def _file_handlers(root: logging.Logger) -> list[logging.Handler]:
    """Handlers that write to a log file, keyed by the resolved file path."""
    seen: set[str] = set()
    out: list[logging.Handler] = []
    for h in root.handlers:
        if not isinstance(h, logging.FileHandler):
            continue
        base = os.path.realpath(h.baseFilename)
        if base not in seen:
            seen.add(base)
            out.append(h)
    return out


def _stderr_handlers(root: logging.Logger) -> list[logging.Handler]:
    """Stream handlers that write to the process stderr."""
    out = []
    for h in root.handlers:
        stream = getattr(h, "stream", None)
        if stream is sys.stderr:
            out.append(h)
    return out


def test_double_bootstrap_same_run_id_no_duplicate_file_handler(
    tmp_path: Path, isolated_root_logger: logging.Logger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bootstrap twice with one run id: the app.jsonl handler stays singular."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    setup = ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )
    setup.bind_run_context("run-42")
    setup.setup_observability(log_path=tmp_path, attach_stderr=False)
    setup.bind_run_context("run-42")
    setup.setup_observability(log_path=tmp_path, attach_stderr=False)

    files = _file_handlers(isolated_root_logger)
    assert files, "the bootstrap must attach the run's file handler"
    assert all(h.baseFilename.endswith("app.jsonl") for h in files)
    assert len(files) == 1, f"double bootstrap duplicated the file handler: {files!r}"


def test_double_bootstrap_same_run_id_no_duplicate_stderr_handler(
    tmp_path: Path, isolated_root_logger: logging.Logger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bootstrap twice in CLI mode: the stderr StreamHandler stays singular."""
    fake_stderr = _FakeStderr()
    monkeypatch.setattr("sys.stderr", fake_stderr)
    setup = ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )
    setup.bind_run_context("run-42")
    setup.setup_observability(log_path=tmp_path, attach_stderr=True)
    setup.bind_run_context("run-42")
    setup.setup_observability(log_path=tmp_path, attach_stderr=True)

    stderrs = _stderr_handlers(isolated_root_logger)
    assert len(stderrs) == 1, f"double bootstrap duplicated the stderr handler: {stderrs!r}"


def test_double_bootstrap_single_record_single_line(
    tmp_path: Path, isolated_root_logger: logging.Logger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After two bootstraps, one record lands in app.jsonl exactly once."""
    monkeypatch.setattr("sys.stderr", _FakeStderr())
    setup = ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )
    setup.bind_run_context("run-42")
    setup.setup_observability(log_path=tmp_path, attach_stderr=False)
    setup.bind_run_context("run-42")
    setup.setup_observability(log_path=tmp_path, attach_stderr=False)

    logging.getLogger().info("single-record-check")
    for h in isolated_root_logger.handlers:
        if isinstance(h, logging.FileHandler):
            h.flush()

    log_file = tmp_path / "app.jsonl"
    lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert sum("single-record-check" in line for line in lines) == 1, (
        "a duplicated handler writes the record more than once"
    )


class _FakeStderr:
    """Stand-in for sys.stderr that records everything written to it."""

    def __init__(self) -> None:
        self.buffer: list[str] = []

    def write(self, data: str) -> int:
        self.buffer.append(data)
        return len(data)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise OSError("no fileno")
