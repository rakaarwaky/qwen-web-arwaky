"""Unit tests for surface_cli_tui_app Tab-per-Job-Slot architecture."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

from textual.widgets import Label, RichLog, TabbedContent

from modules.cli.src.surface_cli_tui_app import NUM_SLOTS, QwenTuiApp
from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler
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

            # The mockup-driven Overview is four cards; the log card is the
            # one element the layout tests keep gated on.
            assert app.query_one("#log-view-overview", RichLog) is not None
            assert app.query_one(".log-card") is not None

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

            # Log views must fit inside the visible tab container. The
            # Overview's log card is the 1fr child of a non-scrolling band, so
            # it takes exactly the rows the engine cards leave and ends at the
            # nav dock — and the band must never grow a scrollbar of its own.
            active_pane = tabs.get_pane("tab-overview")
            overview_log = app.query_one("#log-view-overview", RichLog)
            band = app.query_one("#overview-cards")
            assert overview_log.region.height > 0
            assert overview_log.region.width > 0
            assert overview_log.region.y >= active_pane.region.y
            assert overview_log.region.x >= active_pane.region.x
            assert (
                overview_log.region.y + overview_log.region.height <= active_pane.region.y + active_pane.region.height
            )
            assert overview_log.region.x + overview_log.region.width <= active_pane.region.x + active_pane.region.width
            # Only the log panel scrolls: the Overview itself is one screen.
            assert band.styles.overflow_y == "hidden"

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
            # Load-bearing: the label reaches the Tab widget, not just the model.
            active_tab = app.query_one("#--content-tab-tab-slot-1", Tab)
            assert "deep-review" in str(active_tab.label)

            # The tab strip is hidden (design has no tab bar), so no Tab paints
            # a text row and none of the pane names leak onto screen.
            for w in app.query(Tab):
                assert w.content_region.height == 0, w.id
            for name in ("Overview", "Sessions", "Swarm", "Settings"):
                assert name not in rendered, f"{name} tab label must not paint"
            # The in-page brand row is visible and carries the identity block.
            assert "QWEN-CLI" in rendered

            # The accent active-indicator survives on Textual's Underline.
            underline = tabs.query_one(Underline)
            assert underline.styles.color == accent

    asyncio.run(_run())


# ── Regression: the session verdict must survive a teardown write ───────
#
# The session worker calls _check_session / _apply_session_state from a
# background thread via call_from_thread. When that callback lands while the
# app is tearing down — screen stack popped, timers cancelled — an unguarded
# write used to escape as an app crash. The verdict now goes to the log and
# to _last_session_state instead of a badge widget, so this guards the
# reporting path rather than a widget lookup.


def test_session_check_reports_verdict_without_a_badge_widget() -> None:
    """_check_session reports VALID/EXPIRED/N/A and never needs a widget."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test() as pilot:
            app._session = None
            app._check_session()
            app._apply_session_state("N/A")
            assert app._last_session_state == "N/A"

            # A stored session that validates is reported as VALID.
            app._session = MagicMock()
            app._check_session()
            for _ in range(4):
                await pilot.pause()
            assert app._last_session_state in {"VALID", "EXPIRED"}

            # Teardown state: the timer and log paths must still be safe to
            # hit while the app is shutting down.
            app._session_check_timeout()
            app._session_check_timeout()
            for _ in range(3):
                await pilot.pause()

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


# ── Regression: redesign v6.5.2 widget contract must survive ────────────────
#
# The redesign adds engine-readout cards to the Overview and a view-toggle
# + Clear to the Swarm tab. These tests lock the widget IDs the mockups
# require, the metric-write path, the template-chip shortcut, and the
# log-visibility invariant at the regression-lock size (100x20).


def test_overview_card_ids_exist_on_mount() -> None:
    """The model, swarm, and threads readout widgets must be queryable."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            from textual.widgets import Label

            assert isinstance(app.query_one("#metric-model", Label), Label)
            assert isinstance(app.query_one("#metric-swarm-ring", Label), Label)
            assert isinstance(app.query_one("#metric-swarm-detail", Label), Label)
            assert isinstance(app.query_one("#metric-threads-ring", Label), Label)
            assert isinstance(app.query_one("#metric-threads-detail", Label), Label)
            # Per-card segment bars: the mockup draws one under Swarm Status
            # and one under Chat Status, so the redesign carries two.
            assert isinstance(app.query_one("#metric-swarm-bar", Label), Label)
            assert isinstance(app.query_one("#metric-threads-bar", Label), Label)

    asyncio.run(_run())


def test_flush_metrics_writes_engine_readouts() -> None:
    """_flush_metrics must update the new engine readouts, not only active/done."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)):
            app._slot_stats[1]["status"] = "RUNNING"
            app._slot_stats[2]["status"] = "SUCCESS"
            app._flush_metrics()

            from textual.widgets import Label

            assert str(app.query_one("#metric-active", Label).render()) == "1"
            # Swarm card tracks the swarm engine (0 when idle), not slots.
            assert str(app.query_one("#metric-swarm-ring", Label).render()) == "0/0"
            assert str(app.query_one("#metric-swarm-detail", Label).render()) == "Idle"
            # Uptime is its own trailing readout on the Swarm card, matching
            # the mockup's right-aligned "Uptime Elapsed 21m 53s".
            assert str(app.query_one("#metric-swarm-uptime", Label).render()) == "Uptime Elapsed —"
            # Threads card tracks the per-slot job threads.
            assert str(app.query_one("#metric-threads-ring", Label).render()) == "1/10"
            detail = str(app.query_one("#metric-threads-detail", Label).render())
            assert "1 Running" in detail
            assert "8 Idle" in detail

    asyncio.run(_run())


def test_swarm_toggle_buttons_drive_log_views() -> None:
    """Event / System toggle buttons swap exactly one log view per press."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            from textual.widgets import Button

            event_btn = app.query_one("#btn-swarm-event", Button)
            system_btn = app.query_one("#btn-swarm-system", Button)
            event_log = app.query_one("#log-view-swarm", RichLog)
            system_log = app.query_one("#log-view-swarm-system", RichLog)
            assert event_log.display is True
            assert system_log.display is False

            # Press the system button: only the system log becomes visible and
            # its button carries the active style.
            system_btn.press()
            await pilot.pause()
            for _ in range(4):
                await pilot.pause()
            assert event_log.display is False
            assert system_log.display is True
            assert "toggle-active" in system_btn.classes
            assert "toggle-active" not in event_btn.classes

            # Press the event button: it flips back.
            event_btn.press()
            await pilot.pause()
            for _ in range(4):
                await pilot.pause()
            assert event_log.display is True
            assert system_log.display is False
            assert "toggle-active" in event_btn.classes
            assert "toggle-active" not in system_btn.classes

    asyncio.run(_run())


def test_swarm_clear_button_empties_the_active_log() -> None:
    """Clear drops the buffer and leaves the mockup's flush notice behind."""
    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 40)) as pilot:
            from textual.widgets import Button

            log = app.query_one("#log-view-swarm", RichLog)
            log.write("hello")
            assert log.copy_text() == "hello"

            app.query_one("#btn-clear-swarm-log", Button).press()
            await pilot.pause()
            # The mockup replaces the terminal content with a flushed notice,
            # and the notice is written into the panel that was just cleared.
            flushed = log.copy_text()
            assert "hello" not in flushed
            assert "cleared" in flushed

    asyncio.run(_run())


# ── Regression: one pill click must land on the slot it names ──────────────
#
# Clicking a slot pill focuses that pill, and Textual makes the pane holding
# the focused widget the active tab. Without carrying the focus into the new
# pane, TabPane.Focused pulled the tab straight back to the slot the click
# came from, so the console only moved after several clicks.


def test_slot_pill_click_switches_the_pane_in_one_click() -> None:
    """A pill press shows that slot's pane, and the focus follows it."""
    from textual.widgets import TabbedContent

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            await pilot.click("#nav-chat")
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "tab-slot-1"

            # Each pill press comes from the pane that is currently on screen.
            current = 1
            for target in (5, 2, 7, 1):
                await pilot.click(f"#chat-slot-{current}-{target}")
                for _ in range(3):
                    await pilot.pause(0.02)
                assert tabs.active == f"tab-slot-{target}", target
                current = target

            # The keyboard path is unaffected.
            await pilot.press("alt+9")
            await pilot.pause()
            assert tabs.active == "tab-slot-9"

    asyncio.run(_run())


def test_overview_at_regression_size_keeps_log_visible() -> None:
    """The log panel must still be visible at the regression-lock size 100x20."""
    import asyncio

    app = _make_app()

    async def _run() -> None:
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            for _ in range(15):
                await pilot.pause()
            from textual.widgets import TabbedContent

            pane = app.query_one(TabbedContent).get_pane("tab-overview")
            log = app.query_one("#log-view-overview", RichLog)
            assert log.region.y >= pane.region.y
            assert log.region.height > 0

    asyncio.run(_run())
