"""Unit tests for surface_cli_tui_app Tab-per-Job-Slot architecture."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from textual.widgets import DataTable, Label, RichLog, TabbedContent

from modules.cli.src.surface_cli_tui_app import NUM_SLOTS, QwenTuiApp, QwenTuiLogHandler


def test_tui_app_mounts_and_populates_tabs() -> None:
    app = QwenTuiApp(
        workspace=MagicMock(),
        direct=MagicMock(),
        file_only=MagicMock(),
        attachment=MagicMock(),
        setup=MagicMock(),
        session=MagicMock(),
        jobs=MagicMock(),
    )

    async def _run() -> None:
        async with app.run_test():
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "tab-overview"

            table = app.query_one("#slots-table", DataTable)
            assert table.row_count >= 2

            # Test tab switching actions
            app.action_switch_tab_slot(1)
            assert tabs.active == "tab-slot-1"

            app.action_switch_tab_slot(2)
            assert tabs.active == "tab-slot-2"

            app.action_switch_tab_slot(NUM_SLOTS)
            assert tabs.active == f"tab-slot-{NUM_SLOTS}"

            app.action_switch_tab_overview()
            assert tabs.active == "tab-overview"

            # Test tab label update
            app._set_slot_tab_title(1, "Slot 1: test.md ⏳")
            tab1 = tabs.get_tab("tab-slot-1")
            assert "test.md" in str(tab1.label)

            # Test slot logging
            app._log_msg("Slot 1 specific log", slot_id=1)
            slot_log = app.query_one("#log-view-1", RichLog)
            assert slot_log is not None

            # Test metrics update
            app._slot_stats[1]["status"] = "RUNNING"
            app._refresh_metrics()
            metric_active = app.query_one("#metric-active", Label)
            assert "1" in str(metric_active.render())

    asyncio.run(_run())


def test_log_handler_routes_thread_to_slot() -> None:
    import logging

    mock_app = MagicMock(spec=QwenTuiApp)
    handler = QwenTuiLogHandler(mock_app)

    rec = logging.LogRecord("worker_logger", logging.INFO, "some/path.py", 15, "Worker message", (), None)
    rec.threadName = "qwen_slot_worker_2"

    handler.emit(rec)

    assert mock_app.call_from_thread.called
    args = mock_app.call_from_thread.call_args[0]
    # args[0] is _log_msg, args[1] is formatted string, args[2] is slot_id
    assert "Worker message" in args[1]
    assert args[2] == 2
