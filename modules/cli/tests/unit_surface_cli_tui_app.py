"""Unit tests for surface_cli_tui_app Tab-per-Job-Slot architecture."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import DataTable, Label, RichLog, TabbedContent
from textual.widgets._data_table import CellDoesNotExist

from modules.cli.src.surface_cli_tui_app import NUM_SLOTS, QwenTuiApp
from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler
from modules.cli.src.surface_cli_tui_utils import _TuiUtilsMixin
from modules.cli.src.surface_cli_tui_workers import _TuiWorkersMixin


def _make_app() -> QwenTuiApp:
    # AR-1: slot_config is injected (ISlotRunPlanProtocol), no longer
    # constructed inside the TUI surface.
    return QwenTuiApp(
        workspace=MagicMock(),
        direct=MagicMock(),
        file_only=MagicMock(),
        attachment=MagicMock(),
        slot_config=MagicMock(),
        setup=MagicMock(),
        session=MagicMock(),
        jobs=MagicMock(),
    )


def test_tui_app_mounts_and_populates_tabs() -> None:
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)):
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
            app._set_slot_tab_title(1, "Slot 1: test.md ▶")
            tab1 = tabs.get_tab("tab-slot-1")
            assert "test.md" in str(tab1.label)

            # Test slot logging
            app._log_msg("Slot 1 specific log", slot_id=1)
            slot_log = app.query_one("#log-view-1", RichLog)
            assert slot_log is not None
            assert slot_log.wrap

            # Log views must stay inside the visible tab container.
            active_pane = tabs.get_pane("tab-overview")
            overview_log = app.query_one("#log-view-overview", RichLog)
            assert overview_log.region.height > 0
            assert overview_log.region.width > 0
            assert overview_log.region.y >= active_pane.region.y
            assert overview_log.region.x >= active_pane.region.x
            assert (
                overview_log.region.y + overview_log.region.height <= active_pane.region.y + active_pane.region.height
            )
            assert overview_log.region.x + overview_log.region.width <= active_pane.region.x + active_pane.region.width

            # Test metrics update
            app._slot_stats[1]["status"] = "RUNNING"
            app._flush_metrics()
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


# ── Regression: #slots-table columns must be addressed by KEY, not label ──────
#
# Textual's add_columns("Status") treats the string as a LABEL and auto-generates
# a ColumnKey, so update_cell(row, "Status") raises CellDoesNotExist — which the
# contextlib.suppress in _update_table_row swallows. Result: the dashboard table
# froze at "IDLE / - / 0.0s" forever, and only row_count was ever asserted, so
# the old test passed green. These tests read actual cells.


def test_slots_table_uses_stable_column_keys() -> None:
    """The table's column keys must be the declared ones, not auto-generated."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test():
            table = app.query_one("#slots-table", DataTable)
            assert list(table.columns.keys()) == [
                _TuiUtilsMixin.COL_SLOT,
                _TuiUtilsMixin.COL_STATUS,
                _TuiUtilsMixin.COL_FILE,
                _TuiUtilsMixin.COL_DURATION,
            ]
            # Labels are still what the user sees (Textual stores them as Rich Text).
            assert [str(c.label) for c in table.columns.values()] == ["Slot", "Status", "Prompt File", "Duration"]
            # Cells must be readable BY KEY — this raises CellDoesNotExist if
            # _init_table goes back to label-only add_columns().
            assert table.get_cell("row-slot-1", "status") == "IDLE ●"

    asyncio.run(_run())


def test_slots_table_update_table_row_actually_writes_cells() -> None:
    """_update_table_row must move cells off their IDLE/-/0.0s initial values."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test():
            table = app.query_one("#slots-table", DataTable)
            before = (
                table.get_cell("row-slot-1", "status"),
                table.get_cell("row-slot-1", "file"),
                table.get_cell("row-slot-1", "duration"),
            )
            assert before == ("IDLE ●", "-", "0.0s")

            app._update_table_row(1, "SUCCESS", "task.md", "12.3s")

            after = (
                table.get_cell("row-slot-1", "status"),
                table.get_cell("row-slot-1", "file"),
                table.get_cell("row-slot-1", "duration"),
            )
            assert after == ("SUCCESS", "task.md", "12.3s")
            assert after != before, "_update_table_row was a silent no-op (CellDoesNotExist suppressed?)"
            # The Slot column is untouched.
            assert table.get_cell("row-slot-1", "slot") == "Slot 1"

            # Other rows must not be affected.
            assert table.get_cell("row-slot-2", "status") == "IDLE ●"

    asyncio.run(_run())


def test_slots_table_update_table_row_multi_digit_slot() -> None:
    """row-slot-10 (multi-digit id) resolves too — not just single digits."""
    if NUM_SLOTS < 10:
        pytest.skip(f"app configured with only {NUM_SLOTS} slots")
    app = _make_app()

    async def _run() -> None:
        async with app.run_test():
            table = app.query_one("#slots-table", DataTable)
            app._update_table_row(10, "FAILED", "long-job.md", "1m 4s")
            assert table.get_cell("row-slot-10", "status") == "FAILED"
            assert table.get_cell("row-slot-10", "file") == "long-job.md"
            assert table.get_cell("row-slot-10", "duration") == "1m 4s"

    asyncio.run(_run())


def test_slots_table_tick_elapsed_updates_duration_live() -> None:
    """The live path: a RUNNING slot's Duration cell advances from 'running…'."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test():
            table = app.query_one("#slots-table", DataTable)
            app._slot_stats[1] = {
                "status": "RUNNING",
                "file": "task.md",
                "duration": 0.0,
                "_start_perf": time.perf_counter() - 42,
            }
            app._update_table_row(1, "RUNNING ▶", "task.md", "running…")
            assert table.get_cell("row-slot-1", "duration") == "running…"

            app._tick_elapsed(1)

            assert table.get_cell("row-slot-1", "duration") == "42s"
            assert table.get_cell("row-slot-1", "status") == "RUNNING ▶"

    asyncio.run(_run())


def test_slots_table_update_missing_row_stays_quiet() -> None:
    """Narrow suppression must survive: unknown slot no-ops instead of raising."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test():
            app._update_table_row(999, "SUCCESS", "x.md", "1.0s")  # no raise
            table = app.query_one("#slots-table", DataTable)
            with pytest.raises(CellDoesNotExist):
                table.get_cell("row-slot-999", "status")

    asyncio.run(_run())


# ── Regression: the ACTIVE tab's label must actually render ────────────────────
#
# `Tab.-active { border-bottom: solid $accent }` on a Tab (Textual default
# height:1) consumes the tab's only row — the active tab measured
# content_region.height == 0 and its label vanished behind the highlight.
# The old test asserted `str(tab.label)`, which passes even when nothing is
# drawn. This asserts on composited screen text instead, and pins the
# replacement accent indicator (Textual's Underline, styled via the bare
# type selector — `Tabs > Underline` is a measured no-op on 8.2.8).


def test_active_tab_label_renders_on_screen() -> None:
    """The active tab's relabelled text must reach the rendered screen."""
    from textual.color import Color
    from textual.widgets import Tab
    from textual.widgets._tabs import Underline

    accent = Color.parse("#38bdf8")  # _COLORS["accent"] in surface_cli_tui_css
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-slot-1"
            await pilot.pause()
            app._set_slot_tab_title(1, "Slot 1: deep-review ▶")
            await pilot.pause()

            strips = list(app.screen._compositor.render_strips())
            rendered = "".join(s.text for s in strips)
            # Load-bearing: the label is drawn somewhere on screen.
            assert "deep-review" in rendered

            # …and specifically on the tab row (the strip holding "Overview").
            tab_row = next(s.text for s in strips if "Overview" in s.text)
            assert "deep-review" in tab_row

            # Geometry: the active Tab keeps a full text row; inactive ones are
            # unchanged.
            active_tab = app.query_one("#--content-tab-tab-slot-1", Tab)
            assert active_tab.content_region.height > 0
            for w in app.query(Tab):
                if w.id != "--content-tab-tab-slot-1":
                    assert w.content_region.height == 1, w.id

            # The accent active-indicator survives on Textual's Underline.
            underline = tabs.query_one(Underline)
            assert underline.styles.color == accent

    asyncio.run(_run())


# ── Regression: session-badge writes during teardown must not crash the app ───
#
# The login/session workers call call_from_thread(self._refresh_session_badge)
# (and _apply_session_badge) from background threads. When that callback lands
# while the app is tearing down — badge already unmounted, or screen stack
# popped — query_one raises NoMatches / ScreenStackError. Those are NOT
# subclasses of (LookupError, AttributeError), so the old handlers let them
# escape and run_test re-raised them as an app crash (~1 in 6-8 flaky runs of
# this file). With the badge removed we can reproduce the teardown state
# deterministically.


def test_session_badge_survives_teardown_state() -> None:
    """Badge writers no-op when #session-badge is gone instead of raising NoMatches."""
    from textual.widgets import Label as _Label

    app = _make_app()

    async def _run() -> None:
        async with app.run_test() as pilot:
            # Sanity: on the normal path the badge IS updated (the widened
            # except-clause must not swallow real work).
            app._session = None
            app._refresh_session_badge()
            assert str(app.query_one("#session-badge", _Label).render()) == "N/A"
            app._apply_session_badge(True)
            assert str(app.query_one("#session-badge", _Label).render()) == "VALID"

            # Teardown state: badge unmounted while a queued callback still
            # targets it. Before the fix each of these raised NoMatches.
            app.query_one("#session-badge", _Label).remove()
            for _ in range(3):
                await pilot.pause()

            app._session = MagicMock()  # non-None → refresh takes the CHECKING path
            app._refresh_session_badge()  # must not raise
            app._apply_session_badge(True)  # must not raise
            app._session_check_timeout()  # must not raise (also covers the render() read)

    asyncio.run(_run())


def test_rich_log_copy_text_returns_all_lines() -> None:
    """QwenTuiRichLog.copy_text returns every line's plain text joined by newlines."""
    from modules.cli.src.surface_cli_tui_components import QwenTuiRichLog

    log = QwenTuiRichLog()
    log.write("line one")
    log.write("line two")
    text = log.copy_text()
    lines = text.splitlines()
    assert len(lines) == 2
    assert "line one" in lines[0]
    assert "line two" in lines[1]


def test_rich_log_copy_plain_truncates_to_limit() -> None:
    """QwenTuiRichLog.copy_plain(limit) returns only the last `limit` lines when truncated."""
    from modules.cli.src.surface_cli_tui_components import QwenTuiRichLog

    log = QwenTuiRichLog()
    for i in range(5):
        log.write(f"entry {i}")
    tail = log.copy_plain(limit=2)
    lines = tail.splitlines()
    assert len(lines) == 2
    assert "entry 3" in lines[0]
    assert "entry 4" in lines[1]


def _prime_running_slot(app: QwenTuiApp, slot_id: int, elapsed_sec: float) -> MagicMock:
    """Put a slot into RUNNING state with a live worker and cancel event."""
    worker = MagicMock()
    app._slot_workers[slot_id] = worker
    app._slot_stats[slot_id] = {
        "status": "RUNNING",
        "file": "prompt.md",
        "duration": 0.0,
        "_start_perf": time.perf_counter() - elapsed_sec,
    }
    app._slot_cancel_events[slot_id] = threading.Event()
    return worker


def test_do_cancel_slot_releases_cancel_event_entry() -> None:
    """Issue #331: a cancelled slot must not keep a stale cancel event entry."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)):
            slot_id = 2
            _prime_running_slot(app, slot_id, elapsed_sec=5)
            assert slot_id in app._slot_cancel_events

            app._do_cancel_slot(slot_id)

            assert slot_id not in app._slot_cancel_events
            assert app._slot_workers[slot_id] is None
            assert app._slot_stats[slot_id]["status"] == "CANCELLED"

    asyncio.run(_run())


def test_stale_confirm_modal_cannot_cancel_successor_run() -> None:
    """Issue #331: confirming an old cancel modal must not stop a NEW run.

    Scenario: a >30s run is open → cancel modal is shown but not confirmed;
    the run finishes and a NEW run starts in the same slot; the stale modal
    is then confirmed. The successor run must survive.
    """
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)):
            slot_id = 1
            _prime_running_slot(app, slot_id, elapsed_sec=31)

            captured_cb = None

            def _capture(screen, cb=None):
                nonlocal captured_cb
                captured_cb = cb

            with (
                patch.object(app, "push_screen", side_effect=_capture),
                patch.object(_TuiWorkersMixin, "_do_cancel_slot", autospec=True) as spy,
            ):
                app._cancel_slot(slot_id)
                assert captured_cb is not None

                # Control case: same worker still running → confirm cancels.
                captured_cb(True)
                assert spy.called
                spy.reset_mock()

                # A successor worker took over the slot → stale confirm ignored.
                app._slot_workers[slot_id] = MagicMock()
                captured_cb(True)
                assert not spy.called

                # Declining the modal never cancels.
                app._slot_workers[slot_id] = MagicMock()
                captured_cb(False)
                assert not spy.called

    asyncio.run(_run())


# ── Regression: mobile-web mockup port widgets ────────────────────────────────
#
# These tests pin the new widget IDs introduced by the redesign from
# design/overview_engine_status, design/login_session_manager,
# design/slot_chat_automation_console, and design/swarm_multi_agent_stream:
#   - Overview: #segment-bar + one Static per slot
#   - Sessions: #btn-sessions-login (full-width ADD ACCOUNT)
#   - Swarm:    #btn-stream-view / #btn-log-view / #log-view-swarm-system
#               #unified-stream-container / #full-log-container
#               #btn-clear-swarm-log
#   - Slots:    #btn-templates-{s}
#
# Existing assertions (metrics, tables, log views) must stay green; these
# are additive only.


def test_overview_tab_has_segment_bar_with_one_gfx_per_slot() -> None:
    """#segment-bar renders a block glyph for every configured slot."""
    from textual.containers import Horizontal
    from textual.widgets import Static

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)):
            bar = app.query_one("#segment-bar", Horizontal)
            fills = list(bar.query(Static))
            assert len(fills) == NUM_SLOTS
            for fill in fills:
                assert fill.classes == {"segment-fill", "segment-idle"}

    asyncio.run(_run())


def test_overview_slots_label_stays_outside_the_metric_card() -> None:
    """`Active Job Slots` is its own row, not absorbed into the metric tile.

    Moving the label inside the `.card-inner` Horizontal merged it onto the
    same rendered line as the metric tiles, which is what the mockup's
    separate caption row calls for.
    """
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()

            labels = [w for w in app.query(Label) if "Active Job Slots" in str(w.render())]
            assert len(labels) == 1, "slot caption missing or duplicated"
            caption = labels[0]

            bar = app.query_one("#segment-bar")
            card = next(iter(app.query(".card-inner")))
            # The caption is a sibling of the bar, not a descendant of a card.
            assert caption.parent is not card
            assert caption.parent is bar.parent

            # Distinct rendered rows, caption above the bar.
            assert caption.region.y < bar.region.y

    asyncio.run(_run())


def test_sessions_tab_has_full_width_login_button() -> None:
    """#btn-sessions-login is the full-width primary action above the pool."""
    from textual.widgets import Button

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-sessions"
            await pilot.pause()

            btn = app.query_one("#btn-sessions-login", Button)
            assert btn.label == "＋ ADD ACCOUNT"
            assert "btn-primary-full" in btn.classes
            assert "btn-copy-log" not in btn.classes

    asyncio.run(_run())


def test_sessions_pool_title_row_carries_refresh_button() -> None:
    """#btn-sessions-refresh lives in the ACCOUNT POOL title row."""
    from textual.widgets import Button, TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-sessions"
            await pilot.pause()

            btn = app.query_one("#btn-sessions-refresh", Button)
            assert "🔄 Re-check Tokens" in str(btn.label)
            assert "btn-copy-log" in btn.classes

    asyncio.run(_run())


def test_swarm_tab_has_segmented_log_toggle() -> None:
    """#btn-stream-view is active by default; #btn-log-view is inactive."""
    from textual.widgets import Button, TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-swarm"
            await pilot.pause()

            stream_btn = app.query_one("#btn-stream-view", Button)
            log_btn = app.query_one("#btn-log-view", Button)

            assert "segswitch-active" in stream_btn.classes
            assert "segswitch-active" not in log_btn.classes
            assert "segswitch-btn" in stream_btn.classes
            assert "segswitch-btn" in log_btn.classes

    asyncio.run(_run())


def test_swarm_system_log_is_hidden_by_default() -> None:
    """#full-log-container starts display:none so the system log is invisible."""
    from textual.widgets import TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-swarm"
            await pilot.pause()

            container = app.query_one("#full-log-container")
            assert not container.display

            event_container = app.query_one("#unified-stream-container")
            assert event_container.display

    asyncio.run(_run())


def test_swarm_segmented_toggle_switches_panes() -> None:
    """Clicking SYSTEM LOG shows #full-log-container and hides #unified-stream-container."""
    from textual.widgets import Button, TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-swarm"
            await pilot.pause()

            log_btn = app.query_one("#btn-log-view", Button)
            await pilot.click(log_btn)
            await pilot.pause()

            assert app.query_one("#full-log-container").display
            assert not app.query_one("#unified-stream-container").display
            assert "segswitch-active" in app.query_one("#btn-log-view").classes
            assert "segswitch-active" not in app.query_one("#btn-stream-view").classes

    asyncio.run(_run())


def test_swarm_clear_system_log_flushes_and_writes_receipt() -> None:
    """#btn-clear-swarm-log empties #log-view-swarm-system and writes a receipt."""
    from textual.widgets import Button, RichLog, TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-swarm"
            await pilot.pause()

            # Switch to system log so the pane is visible.
            log_btn = app.query_one("#btn-log-view", Button)
            await pilot.click(log_btn)
            await pilot.pause()

            view = app.query_one("#log-view-swarm-system", RichLog)
            view.write("[red]pre-existing line[/red]")
            assert len(view.lines) > 0

            clear_btn = app.query_one("#btn-clear-swarm-log", Button)
            await pilot.click(clear_btn)
            await pilot.pause()

            text = view.copy_text()
            assert "Logs flushed by user" in text
            assert "pre-existing line" not in text

    asyncio.run(_run())


def test_slot_template_sheet_button_exists_and_logs() -> None:
    """#btn-templates-{s} reports the role count into that slot's own log.

    The button lives below the fold in the scrollable left pane, so the
    click path can't reach it at this terminal size; the handler is driven
    directly, which is the same code path the button press takes.
    """
    from textual.widgets import Button, RichLog, TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-slot-1"
            await pilot.pause()

            btn = app.query_one("#btn-templates-1", Button)
            assert btn.label == "OPEN"
            assert "btn-copy-log" in btn.classes

            slot_log = app.query_one("#log-view-1", RichLog)
            assert "TEMPLATES: Slot 1" not in slot_log.copy_text()

            app._open_template_sheet(1)
            await pilot.pause()

            after = slot_log.copy_text()
            assert "TEMPLATES: Slot 1" in after
            assert "roles available" in after

    asyncio.run(_run())


def test_swarm_action_deck_buttons_exist() -> None:
    """#btn-swarm-start and #btn-swarm-cancel are wired inside the swarm pane."""
    from textual.widgets import Button, TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.active = "tab-swarm"
            await pilot.pause()

            start = app.query_one("#btn-swarm-start", Button)
            cancel = app.query_one("#btn-swarm-cancel", Button)

            assert start.label == "▶ START"
            assert "btn-start" in start.classes
            assert cancel.label == "■ STOP"
            assert "btn-stop" in cancel.classes

    asyncio.run(_run())
