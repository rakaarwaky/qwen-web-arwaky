"""Regression tests: interactive TUI must not leak logs to stderr.

The interactive TUI owns the terminal canvas. Playwright browser callbacks
run on their own threads and emit log records (browser_mutation_response,
browser_request_failed, ...). If observability attaches a stderr
StreamHandler, those records are written straight to the terminal and
corrupt the TUI — the "log appears above the log area" bug.

See PR that introduced attach_stderr=False for the interactive path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from modules.core.src.capabilities_metrics_counter import MetricsCounter
from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.capabilities_status_writer import StatusFileWriter
from modules.shared.src.utility_core_status import status_path_for


@pytest.fixture
def isolated_root_logger():
    """Snapshot and restore the root logger's handlers/level."""
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


def _stderr_handlers(root: logging.Logger) -> list[logging.Handler]:
    """Handlers that write to the process stderr (FileHandler excluded)."""
    import sys

    out = []
    for h in root.handlers:
        stream = getattr(h, "stream", None)
        if stream is None:
            continue
        if isinstance(h, logging.FileHandler):
            continue
        if stream is sys.stderr:
            out.append(h)
    return out


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


def test_interactive_mode_attaches_no_stderr_handler(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """attach_stderr=False must leave the root logger without a stderr handler."""
    monkeypatch.setattr("sys.stderr", _FakeStderr())
    cap = ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )

    cap.setup_observability(log_path=tmp_path, attach_stderr=False)

    assert _stderr_handlers(isolated_root_logger) == [], "interactive mode must not attach a stderr StreamHandler"


def test_cli_mode_still_attaches_stderr_handler(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """Non-interactive CLI runs keep the stderr handler for operator visibility."""
    fake = _FakeStderr()
    monkeypatch.setattr("sys.stderr", fake)
    cap = ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )

    cap.setup_observability(log_path=tmp_path, attach_stderr=True)

    assert _stderr_handlers(isolated_root_logger) != [], "CLI mode must keep its stderr handler"


def test_browser_logs_do_not_reach_stderr_in_tui_mode(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """The exact startup scenario: browser callbacks emit while the TUI runs."""
    fake = _FakeStderr()
    monkeypatch.setattr("sys.stderr", fake)
    cap = ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )
    cap.setup_observability(log_path=tmp_path, attach_stderr=False)

    # Replay what Playwright's page.on("response") callback emits during the
    # startup session check (capabilities_browser_adapter).
    log = cap.get_logger("capabilities_browser_adapter")
    log.info("browser_mutation_response", status=200, url="https://chat.qwen.ai/api/chat")
    log.warning("browser_request_failed", url="https://chat.qwen.ai/x", error="net::ERR_NAME_NOT_RESOLVED")

    leaked = "".join(fake.buffer)
    assert "browser_mutation_response" not in leaked, "browser log leaked to stderr in TUI mode"
    assert "browser_request_failed" not in leaked, "browser log leaked to stderr in TUI mode"


def test_browser_logs_still_persist_to_file_in_tui_mode(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """Disabling stderr must not drop operational logging — app.jsonl still written."""
    fake = _FakeStderr()
    monkeypatch.setattr("sys.stderr", fake)
    cap = ObservabilitySetup(
        tmp_path,
        StatusFileWriter(status_path_for(tmp_path)),
        MetricsCounter(metrics_path=tmp_path / "metrics.json"),
    )
    cap.setup_observability(log_path=tmp_path, attach_stderr=False)

    log = cap.get_logger("capabilities_browser_adapter")
    log.info("browser_mutation_response", status=200, url="https://chat.qwen.ai/api/chat")

    for h in isolated_root_logger.handlers:
        if isinstance(h, logging.Handler):
            h.flush()
    app_log = tmp_path / "app.jsonl"
    assert app_log.exists(), "app.jsonl must still be written when stderr is disabled"
    content = app_log.read_text(encoding="utf-8")
    assert "browser_mutation_response" in content, "browser log must reach the JSONL file"
