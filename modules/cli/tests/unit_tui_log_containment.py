"""Comprehensive regression suite: TUI log containment.

Background
----------
The TUI owns the terminal canvas. Two independent classes of bug historically
let log text escape the "System Event Log" panel and paint raw text over the
UI (reported as "logs appear above the log area at startup"):

1. **Stderr leak** (PR #251). The interactive path called
   ``setup_observability()`` which attaches ``StreamHandler(sys.stderr)``.
   The startup session check launches a headless browser; Playwright's
   ``page.on("response")``/``on("requestfailed")`` callbacks emit records
   from *their own threads*, which went straight to the terminal.

2. **Layout squeeze** (PRs #249/#250). ``#slots-table`` (10 rows) claimed
   every available row on short terminals, leaving the log panel 0 height.

This suite locks both: no log may reach the process stderr while the TUI
runs, logs must land inside the bordered RichLog panels, and the log panel
must stay visible across terminal sizes.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from textual.widgets import RichLog

from modules.cli.src.surface_cli_tui_app import NUM_SLOTS, QwenTuiApp
from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler
from modules.core.src.capabilities_observability_setup import ObservabilitySetup

# ── Fixtures ──────────────────────────────────────────────────────────────────


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


def _stderr_handlers(root: logging.Logger) -> list[logging.Handler]:
    """Handlers writing to the process stderr (FileHandler excluded)."""
    out = []
    for h in root.handlers:
        stream = getattr(h, "stream", None)
        if stream is None or isinstance(h, logging.FileHandler):
            continue
        if stream is sys.stderr:
            out.append(h)
    return out


def _make_app() -> QwenTuiApp:
    return QwenTuiApp(
        workspace=_NoOp(),
        direct=_NoOp(),
        file_only=_NoOp(),
        attachment=_NoOp(),
        slot_config=_NoOp(),
        setup=_NoOp(),
        session=_NoOp(),
        jobs=_NoOp(),
        swarm=_NoOp(),
    )


class _NoOp:
    """MagicMock stand-in that is picklable-free and cheap."""

    def __getattr__(self, _name: str) -> Any:
        return _NoOp()

    def __call__(self, *_a: Any, **_k: Any) -> Any:
        return _NoOp()


def _tui_observability(tmp_path: Path) -> ObservabilitySetup:
    """Observability configured exactly like the interactive TUI path."""
    cap = ObservabilitySetup(tmp_path)
    cap.setup_observability(log_path=tmp_path, attach_stderr=False)
    return cap


# ── Part 1: the stderr handler must not exist in TUI mode ─────────────────────


def test_tui_mode_attaches_no_stderr_handler(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """attach_stderr=False leaves the root logger without a stderr handler."""
    monkeypatch.setattr(sys, "stderr", _FakeStderr())
    _tui_observability(tmp_path)

    assert _stderr_handlers(isolated_root_logger) == [], "TUI mode must not attach a stderr StreamHandler"


def test_cli_mode_keeps_stderr_handler(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """Non-interactive CLI runs keep the stderr handler for operator visibility."""
    monkeypatch.setattr(sys, "stderr", _FakeStderr())
    ObservabilitySetup(tmp_path).setup_observability(log_path=tmp_path, attach_stderr=True)

    assert _stderr_handlers(isolated_root_logger) != [], "CLI mode must keep its stderr handler"


def test_default_is_stderr_enabled(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """The default must stay backwards-compatible: stderr attached."""
    monkeypatch.setattr(sys, "stderr", _FakeStderr())
    ObservabilitySetup(tmp_path).setup_observability(log_path=tmp_path)

    assert _stderr_handlers(isolated_root_logger) != []


# ── Part 2: every browser event that fires at startup must not leak ───────────
#
# These are the exact records capabilities_browser_adapter emits during the
# startup session check (page.on handlers + navigate_to_chat).


_BROWSER_EVENTS: list[tuple[str, int, dict[str, Any]]] = [
    ("browser_mutation_request", logging.INFO, {"method": "POST", "url": "https://chat.qwen.ai/api/chat"}),
    ("browser_mutation_response", logging.INFO, {"status": 200, "url": "https://chat.qwen.ai/api/chat"}),
    ("browser_request_failed", logging.WARNING, {"url": "https://chat.qwen.ai/x", "error": "net::ERR_FAILED"}),
    ("browser_http_error", logging.WARNING, {"status": 500, "url": "https://chat.qwen.ai/api/generate"}),
    ("browser_console_message", logging.WARNING, {"type": "error", "text": "Uncaught TypeError"}),
    ("browser_context_cleanup_failed", logging.WARNING, {"error": "already closed"}),
    ("browser_eager_navigate_ok", logging.DEBUG, {"url": "https://chat.qwen.ai"}),
]


@pytest.mark.parametrize("event,level,extra", _BROWSER_EVENTS)
def test_browser_event_never_leaks_to_stderr(
    event: str, level: int, extra: dict[str, Any], tmp_path: Path, isolated_root_logger, monkeypatch
) -> None:
    """Each Playwright-callback record must stay out of the terminal."""
    fake = _FakeStderr()
    monkeypatch.setattr(sys, "stderr", fake)
    cap = _tui_observability(tmp_path)
    log = cap.get_logger("capabilities_browser_adapter")

    # structlog-style kwargs and stdlib-style args both must be safe.
    getattr(log, logging.getLevelName(level).lower())(event, **extra)

    leaked = "".join(fake.buffer)
    assert event not in leaked, f"{event} leaked to stderr in TUI mode"


def test_all_browser_events_fired_together_do_not_leak(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """The full startup burst, emitted back-to-back."""
    fake = _FakeStderr()
    monkeypatch.setattr(sys, "stderr", fake)
    cap = _tui_observability(tmp_path)
    log = cap.get_logger("capabilities_browser_adapter")

    for event, level, extra in _BROWSER_EVENTS:
        getattr(log, logging.getLevelName(level).lower())(event, **extra)

    leaked = "".join(fake.buffer)
    for event, _, _ in _BROWSER_EVENTS:
        assert event not in leaked


def test_browser_events_from_worker_threads_do_not_leak(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """Playwright callbacks run on their own threads — the real bug vector."""
    fake = _FakeStderr()
    monkeypatch.setattr(sys, "stderr", fake)
    cap = _tui_observability(tmp_path)
    log = cap.get_logger("capabilities_browser_adapter")

    barrier = threading.Barrier(4)
    errors: list[BaseException] = []

    def _fire(name: str) -> None:
        try:
            barrier.wait(timeout=5)
            for _ in range(10):
                log.info("browser_mutation_response", status=200, url=f"https://chat.qwen.ai/{name}")
                log.warning("browser_request_failed", url=f"https://chat.qwen.ai/{name}", error="boom")
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_fire, args=(f"t{i}",), daemon=True) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, errors
    leaked = "".join(fake.buffer)
    assert "browser_mutation_response" not in leaked
    assert "browser_request_failed" not in leaked


def test_error_level_records_do_not_leak_to_stderr(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """Even ERROR records must not corrupt the canvas in TUI mode."""
    fake = _FakeStderr()
    monkeypatch.setattr(sys, "stderr", fake)
    cap = _tui_observability(tmp_path)
    cap.get_logger("agent_session_orchestrator").error("session_check_crashed", error="boom")

    assert "session_check_crashed" not in "".join(fake.buffer)


# ── Part 3: disabling stderr must not drop operational logging ────────────────


def test_app_jsonl_still_written_in_tui_mode(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """app.jsonl must still receive every record when stderr is disabled."""
    monkeypatch.setattr(sys, "stderr", _FakeStderr())
    cap = _tui_observability(tmp_path)
    cap.get_logger("capabilities_browser_adapter").info("browser_mutation_response", status=200)

    for h in isolated_root_logger.handlers:
        h.flush()
    content = (tmp_path / "app.jsonl").read_text(encoding="utf-8")
    assert "browser_mutation_response" in content


def test_all_levels_persist_to_file_in_tui_mode(tmp_path: Path, isolated_root_logger, monkeypatch) -> None:
    """INFO+ must reach the JSONL file (DEBUG only when verbose)."""
    monkeypatch.setattr(sys, "stderr", _FakeStderr())
    cap = _tui_observability(tmp_path)
    log = cap.get_logger("capabilities_browser_adapter")
    log.info("browser_mutation_response", status=200)
    log.warning("browser_request_failed", error="x")
    log.error("browser_http_error", status=500)

    for h in isolated_root_logger.handlers:
        h.flush()
    content = (tmp_path / "app.jsonl").read_text(encoding="utf-8")
    assert "browser_mutation_response" in content
    assert "browser_request_failed" in content
    assert "browser_http_error" in content


# ── Part 4: the TUI log handler routes records into the widgets ───────────────


def test_tui_log_handler_routes_browser_record_to_overview() -> None:
    """A browser record must be dispatched to _log_msg, not to the terminal."""
    from unittest.mock import MagicMock

    app = MagicMock(spec=QwenTuiApp)
    handler = QwenTuiLogHandler(app)

    rec = logging.LogRecord(
        "capabilities_browser_adapter",
        logging.INFO,
        "capabilities_browser_adapter.py",
        560,
        "browser_mutation_response",
        (),
        None,
    )
    handler.emit(rec)

    assert app.call_from_thread.called
    args = app.call_from_thread.call_args[0]
    # args = (_log_msg, text, slot_id)
    assert args[0] == app._log_msg
    assert "browser_mutation_response" in str(args[1])
    assert args[2] is None  # overview (not a slot worker thread)


def test_tui_log_handler_truncates_long_records() -> None:
    """Long records are truncated so they cannot overflow the panel horizontally."""
    from unittest.mock import MagicMock

    app = MagicMock(spec=QwenTuiApp)
    handler = QwenTuiLogHandler(app)

    long_msg = "x" * 500
    rec = logging.LogRecord("capabilities_browser_adapter", logging.INFO, "p.py", 1, long_msg, (), None)
    handler.emit(rec)

    text = app.call_from_thread.call_args[0][1]
    assert len(str(text)) <= 250


def test_tui_log_handler_ignores_third_party_records() -> None:
    """urllib3/playwright/httpx noise must not flood the TUI views."""
    from unittest.mock import MagicMock

    app = MagicMock(spec=QwenTuiApp)
    handler = QwenTuiLogHandler(app)

    for noisy in ("urllib3.connectionpool", "playwright._impl", "httpx._client", "asyncio"):
        rec = logging.LogRecord(noisy, logging.INFO, "p.py", 1, "noise", (), None)
        assert handler.filter(rec) is False, f"{noisy} must be filtered out"

    for allowed in ("", "qwen-web", "modules.core.src.capabilities_browser_adapter", "browser"):
        rec = logging.LogRecord(allowed, logging.INFO, "p.py", 1, "keep", (), None)
        assert handler.filter(rec) is True, f"{allowed!r} must be allowed"


# ── Part 5: end-to-end — run the real TUI while browser logs fire ─────────────


def test_tui_app_contains_browser_logs_in_panels() -> None:
    """Browser records emitted during a live TUI run land in the log panel.

    This exercises the same path the real startup session check uses:
    QwenTuiLogHandler.emit -> app.call_from_thread -> _log_msg -> RichLog.
    """
    import asyncio

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # Attach exactly like _deferred_startup does.
            from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler

            handler = QwenTuiLogHandler(app)
            logging.getLogger().addHandler(handler)
            try:
                # Emit from a worker thread, exactly like Playwright callbacks.
                def _fire() -> None:
                    for name, level, msg in [
                        ("capabilities_browser_adapter", logging.INFO, "browser_mutation_response"),
                        ("capabilities_browser_adapter", logging.WARNING, "browser_request_failed"),
                    ]:
                        rec = logging.LogRecord(name, level, "capabilities_browser_adapter.py", 560, msg, (), None)
                        logging.getLogger().handle(rec)

                t = threading.Thread(target=_fire)
                t.start()
                t.join(timeout=5)
                for _ in range(15):
                    await pilot.pause()
            finally:
                logging.getLogger().removeHandler(handler)

            # The records must have been routed INTO the Overview panel.
            overview = app.query_one("#log-view-overview", RichLog)
            rendered = "\n".join(str(ln) for ln in overview.lines)
            assert "browser_mutation_response" in rendered, "record must reach the Overview log panel"
            assert "browser_request_failed" in rendered

    asyncio.run(_run())


# ── Part 6: layout — the log panel must stay visible at any terminal size ─────


_TERM_SIZES = [(100, 40), (100, 30), (120, 24), (100, 22), (80, 24), (100, 20), (80, 20)]


@pytest.mark.parametrize("cols,rows", _TERM_SIZES)
def test_log_panel_always_visible(cols: int, rows: int) -> None:
    """The System Event Log panel must render with >0 height on any size."""
    import asyncio

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(cols, rows)) as pilot:
            await pilot.pause()
            for _ in range(15):
                await pilot.pause()
            log = app.query_one("#log-view-overview", RichLog)
            assert log.region.height > 0, f"log panel has 0 height at {cols}x{rows}"
            assert log.region.width > 0

    asyncio.run(_run())


@pytest.mark.parametrize("cols,rows", _TERM_SIZES)
def test_log_panel_stays_inside_tab_pane(cols: int, rows: int) -> None:
    """The log panel must be visible within (or reachable through) its tab pane.

    On tall terminals the panel fits entirely inside the pane. On short ones
    the pane scrolls, so the requirement is that the panel is laid out inside
    the pane's scrollable content area — i.e. it starts within the pane and
    is reachable — never painted over the tabs/header above it.
    """
    import asyncio

    from textual.widgets import TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(cols, rows)) as pilot:
            await pilot.pause()
            for _ in range(15):
                await pilot.pause()
            tabs = app.query_one(TabbedContent)
            pane = tabs.get_pane("tab-overview")
            log = app.query_one("#log-view-overview", RichLog)
            # Never painted above or left of the pane (the original bug:
            # logs rendering over the tab bar / header area).
            assert log.region.y >= pane.region.y, (
                f"log panel starts above the pane at {cols}x{rows}: log.y={log.region.y} pane.y={pane.region.y}"
            )
            assert log.region.x >= pane.region.x
            # And it must occupy real, visible rows.
            assert log.region.height > 0
            assert log.region.width > 0

    asyncio.run(_run())


def test_slots_table_never_squeezes_log_panel_to_zero() -> None:
    """The regression itself: table rows must not eat the whole pane."""
    import asyncio

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            for _ in range(15):
                await pilot.pause()
            from textual.widgets import DataTable

            table = app.query_one("#slots-table", DataTable)
            log = app.query_one("#log-view-overview", RichLog)
            # Table is capped and scrolls; the log panel keeps real estate.
            assert table.region.height < 12
            assert log.region.height >= 1

    asyncio.run(_run())


# ── Part 7: long lines must wrap, not widen the panel ─────────────────────────


def test_richlog_views_have_wrapping_enabled() -> None:
    """wrap=True prevents long records from pushing the panel wider."""
    import asyncio

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for view_id in ["#log-view-overview", "#log-view-swarm"] + [
                f"#log-view-{s}" for s in range(1, NUM_SLOTS + 1)
            ]:
                try:
                    view = app.query_one(view_id, RichLog)
                except Exception:
                    continue
                assert view.wrap, f"{view_id} must have wrap=True"

    asyncio.run(_run())
