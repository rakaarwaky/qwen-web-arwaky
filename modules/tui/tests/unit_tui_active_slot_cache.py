"""Regression tests for FE-4-01: cached active slot id for log fan-out.

``_log_msg`` with ``slot_id=None`` used to call ``_get_active_slot_id()``,
which ran ``query_one(TabbedContent)`` plus a string parse **per log
record**. During a 10-slot swarm that is dozens of DOM queries per second.

The active slot id is now cached in ``_active_slot_cache`` (default 1 —
the historical no-slot fallback; never 0, which is the Overview log).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from modules.tui.src.surface_tui_app_screen import QwenTuiApp
from modules.tui.tests.fixture_tui_app import make_app


class TestActiveSlotCacheContract:
    def test_mro_exposes_refresh_helper(self) -> None:
        assert hasattr(QwenTuiApp, "_refresh_active_slot_cache")
        assert hasattr(QwenTuiApp, "on_tabbed_content_tab_activated")

    def test_default_cache_is_one(self) -> None:
        app = make_app()
        assert app._active_slot_cache == 1
        assert app._get_active_slot_id() == 1


class TestZeroQueryUnscopedLogs:
    def test_100_unscoped_logs_perform_zero_query_one(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                from textual.widgets import TabbedContent

                tabs = app.query_one(TabbedContent)
                app._refresh_active_slot_cache()

                calls = {"n": 0}
                original = app.query_one

                def counting_query_one(*args, **kwargs):
                    target = args[0] if args else kwargs.get("selector")
                    if target is TabbedContent or (isinstance(target, type) and target.__name__ == "TabbedContent"):
                        calls["n"] += 1
                    return original(*args, **kwargs)

                app.query_one = counting_query_one
                try:
                    for i in range(100):
                        app._log_msg(f"unscoped record {i}")
                finally:
                    app.query_one = original

                assert calls["n"] == 0, f"expected 0 TabbedContent query_one calls, got {calls['n']}"
                assert tabs.active is not None

        asyncio.run(_run())


class TestCacheTracksTabSwitches:
    def test_programmatic_switch_updates_cache(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                from textual.widgets import TabbedContent

                tabs = app.query_one(TabbedContent)

                app._switch_to_slot(3)
                await pilot.pause(0.1)
                assert tabs.active == "tab-slot-3"
                assert app._active_slot_cache == 3

                app.set_focus(None)
                await pilot.pause(0.05)

                app.action_switch_tab_overview()
                await pilot.pause(0.1)
                assert tabs.active == "tab-overview"
                assert app._active_slot_cache == 1

                app.action_switch_tab_swarm()
                await pilot.pause(0.1)
                assert tabs.active == "tab-swarm"
                assert app._active_slot_cache == 1

                app.action_switch_tab_settings()
                await pilot.pause(0.1)
                assert tabs.active == "tab-settings"
                assert app._active_slot_cache == 1

                app.set_focus(None)
                await pilot.pause(0.05)
                app._switch_to_slot(5)
                await pilot.pause(0.1)
                assert app._active_slot_cache == 5

        asyncio.run(_run())

    def test_nav_dock_go_updates_cache(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                from textual.widgets import TabbedContent

                tabs = app.query_one(TabbedContent)

                app._nav_dock_go("nav-chat")
                await pilot.pause(0.1)
                assert tabs.active.startswith("tab-slot-")
                assert app._active_slot_cache == int(tabs.active.split("-")[-1])

                app._nav_dock_go("nav-swarm")
                await pilot.pause(0.1)
                assert tabs.active == "tab-swarm"
                assert app._active_slot_cache == 1

        asyncio.run(_run())

    def test_stale_tab_activated_event_cannot_walk_cache_backwards(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                from textual.widgets import TabbedContent

                tabs = app.query_one(TabbedContent)

                app._switch_to_slot(7)
                await pilot.pause(0.1)
                assert app._active_slot_cache == 7
                assert tabs.active == "tab-slot-7"

                stale = MagicMock()
                stale.tab = MagicMock()
                stale.tab.id = "tab-slot-2"
                app.on_tabbed_content_tab_activated(stale)
                await pilot.pause(0.05)

                assert app._active_slot_cache == 7
                assert tabs.active == "tab-slot-7"

        asyncio.run(_run())

    def test_log_routes_to_slot_after_programmatic_switch(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                app._switch_to_slot(4)
                await pilot.pause(0.1)
                assert app._get_active_slot_id() == 4

                views = getattr(app, "_log_views", {})
                target = views.get(4)
                assert target is not None, f"slot 4 log view missing; views={list(views)}"

                written: list[str] = []
                original_write = target.write

                def _write(msg, *a, **k):
                    written.append(str(msg))
                    return original_write(msg, *a, **k)

                target.write = _write
                app._log_msg("routed to slot 4")
                assert any("routed to slot 4" in w for w in written), written

        asyncio.run(_run())

    def test_refresh_falls_back_to_one_when_query_raises(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app._active_slot_cache = 9

                def _boom(*args, **kwargs):
                    raise RuntimeError("DOM gone")

                original = app.query_one
                app.query_one = _boom
                try:
                    app._refresh_active_slot_cache()
                finally:
                    app.query_one = original

                assert app._active_slot_cache == 1

        asyncio.run(_run())


__all__ = [
    "TestActiveSlotCacheContract",
    "TestZeroQueryUnscopedLogs",
    "TestCacheTracksTabSwitches",
]
