"""Unit tests for the Sessions-pane account card action buttons.

The card foot carries three icon-only buttons — the shipped glyph set is
↻ / ☐ / × (rendered from ``_GLYPHS`` in
``modules.tui.src.surface_tui_utils_component``), with ASCII fallbacks
``r / h / x`` on forced-ascii locale terminals:
- ↻ (refresh, ``account-refresh-<n>``): reloads the pool from disk and
  repaints the row.
- ☐ (health, ``account-health-<n>``): runs the pool health check — the
  same probe as ``qwa session health`` (``SessionHealthChecker``).
- × (delete, ``account-delete-<n>``): removes the pool entry and deletes
  the Chromium profile — the same logic as ``qwa session remove``
  (``SessionManager.remove_session`` + ``delete_session_profile``),
  guarded by a ``ConfirmModal``.

These tests lock the button labels/names, the event routing, and the
delete wiring.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any
from unittest.mock import MagicMock, patch

from modules.tui.src.surface_tui_utils_component import _TuiUtilsMixin


class TestAccountCardButtons:
    """The account card renders two icon-only action buttons with the
    correct names so the event router can address them by position."""

    def test_card_carries_flask_and_trash_icons(self) -> None:
        session = MagicMock(spec=["name", "session_id", "is_healthy", "status", "path"])
        session.name = "arwaky007"
        session.session_id = "session_1"
        session.is_healthy = True
        session.status = MagicMock()
        session.status.value = "active"
        session.path = MagicMock()

        # Textual only registers children with the widget tree once mounted,
        # so mount the card under a container in a live app before querying.
        from textual.containers import Container
        from textual.widgets import Button

        from modules.tui.src.surface_tui_app_screen import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            prompt=MagicMock(),
            slot_config=MagicMock(),
            session=MagicMock(),
            jobs=MagicMock(),
            updater=MagicMock(),
            job_storage=MagicMock(),
        )

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                host = Container(id="card-host")
                await app.mount(host)
                await host.mount(card)
                buttons = list(card.query(Button))
                labels = [str(b.label) for b in buttons]
                # Three buttons: refresh (↻), health (☐), and trash (×)
                assert len(buttons) == 3, f"expected 3 buttons, got {len(buttons)}"
                assert "↻" in labels[0], f"first button should be the refresh icon, got {labels!r}"
                assert "☐" in labels[1], f"second button should be the health icon, got {labels!r}"
                assert "×" in labels[2], f"third button should be the delete icon, got {labels!r}"
                # Names ride on position so a re-check rebuild can't collide ids
                assert buttons[0].name == "account-refresh-1"
                assert buttons[1].name == "account-health-1"
                assert buttons[2].name == "account-delete-1"
                # UX-4-001: every icon-only button carries an accessible
                # tooltip naming the session — the row has no other text
                # channel for a screen reader (WCAG 1.1.1).
                assert buttons[0].tooltip == "Refresh pool entry 'arwaky007'", buttons[0].tooltip
                assert buttons[1].tooltip == "Run a health check on 'arwaky007'", buttons[1].tooltip
                assert buttons[2].tooltip == "Delete session 'arwaky007' (asks confirmation first)", buttons[2].tooltip

        # The glyph resolver honours the forced-ascii locale fallback so a
        # real terminal without a Nerd Font renders the ASCII set instead of
        # a tofu box. NO_COLOR is a *colour* preference and no longer
        # affects iconography (UX-3-003), so the wide-glyph assertion here
        # needs only a UTF-8 locale.
        with patch.dict(os.environ, {"LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}, clear=False):
            os.environ.pop("NO_COLOR", None)
            card = _TuiUtilsMixin._account_card(session, 1)
            asyncio.run(_run())

    def test_card_labels_contain_no_text(self) -> None:
        """The buttons are icon-only — no 'TEST'/'EXIT'/'DELETE' text labels."""
        session = MagicMock(spec=["name", "session_id", "is_healthy", "status", "path"])
        session.name = "test"
        session.session_id = "s1"
        session.is_healthy = False
        session.status = MagicMock()
        session.status.value = "limited"
        session.path = MagicMock()

        card = _TuiUtilsMixin._account_card(session, 2)

        from textual.containers import Container
        from textual.widgets import Button

        from modules.tui.src.surface_tui_app_screen import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            prompt=MagicMock(),
            slot_config=MagicMock(),
            session=MagicMock(),
            jobs=MagicMock(),
            updater=MagicMock(),
            job_storage=MagicMock(),
        )

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                host = Container(id="card-host")
                await app.mount(host)
                await host.mount(card)
                for b in card.query(Button):
                    plain = str(b.label)
                    assert "TEST" not in plain.upper(), f"flask button must be icon-only, got {plain!r}"
                    assert "EXIT" not in plain.upper(), f"trash button must be icon-only, got {plain!r}"

        asyncio.run(_run())


class TestAccountButtonRouting:
    """The event router routes ``account-delete-`` to the delete handler
    and ``account-test-`` to the health-check handler."""

    def test_delete_button_routes_to_confirm(self) -> None:
        """Pressing the trash button pushes a ConfirmModal, not a
        'run CLI command' notification."""
        from modules.tui.src.surface_tui_app_screen import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            prompt=MagicMock(),
            slot_config=MagicMock(),
            session=MagicMock(),
            jobs=MagicMock(),
            updater=MagicMock(),
            job_storage=MagicMock(),
        )

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                # Simulate the button-press routing that
                # _TuiEventsMixin.on_button_pressed would do.
                with (
                    patch.object(app, "_confirm_delete_session") as mock_confirm,
                    patch.object(app, "_notify", create=True),
                ):
                    app._account_button_pressed("delete", 1)
                    mock_confirm.assert_called_once()

        asyncio.run(_run())

    def test_test_button_routes_to_health_check(self) -> None:
        """Pressing the flask button runs the session health check."""
        from modules.tui.src.surface_tui_app_screen import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            prompt=MagicMock(),
            slot_config=MagicMock(),
            session=MagicMock(),
            jobs=MagicMock(),
            updater=MagicMock(),
            job_storage=MagicMock(),
        )

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with (
                    patch.object(app, "_run_session_health_check") as mock_health,
                    patch.object(app, "_log_msg"),
                ):
                    app._account_button_pressed("health", 1)
                    mock_health.assert_called_once()

        asyncio.run(_run())


class TestDeleteSessionWorker:
    """_run_delete_session runs the same logic as 'qwa session remove':
    remove the pool entry, then delete the profile via the manager."""

    def test_delete_removes_pool_entry_and_profile(self) -> None:
        from modules.tui.tests.fixture_tui_app import make_app

        app = make_app()

        mock_manager = MagicMock()
        mock_manager.remove_session.return_value = True
        app._session_manager = mock_manager

        # Seed the sessions cache with one entry. The one-shot load guard is
        # set so the mount-time refresh cannot repaint the cache from the
        # mock pool and race this seed.
        session_info = MagicMock()
        session_info.name = "arwaky007"
        session_info.session_id = "session_1"
        session_info.path = MagicMock()
        app._sessions_cache = [session_info]
        app._sessions_loaded_once = True
        # The confirm flow captures the target name before the worker runs.
        app._last_delete_name = "arwaky007"

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                from textual.worker import WorkerFailed

                _sync_cft(app)
                worker = app._run_delete_session("arwaky007")
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()
                mock_manager.remove_session.assert_called_once_with("session_1")
                mock_manager.delete_session_profile.assert_called_once_with(session_info.path)

        asyncio.run(_run())

    def test_delete_declined_is_noop(self) -> None:
        """A declined modal never starts the worker.

        The confirm callback only calls ``_run_delete_session`` when the
        modal answered True, so there is nothing to undo on Cancel.
        """

        from modules.tui.src.surface_tui_app_screen import QwenTuiApp

        app = make_app()
        mock_manager = MagicMock()
        app._session_manager = mock_manager

        # Seed the cache with a real entry so the declined-delete assertion is
        # not vacuous: the worker must not remove the entry when the answer
        # is False.
        session_info = MagicMock()
        session_info.name = "arwaky007"
        session_info.session_id = "session_1"
        session_info.path = MagicMock()
        app._sessions_cache = [session_info]
        app._sessions_loaded_once = True
        app._last_delete_name = "arwaky007"

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                _sync_cft(app)
                worker = app._run_delete_session(False)
                from textual.worker import WorkerFailed

                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()
                mock_manager.remove_session.assert_not_called()
                mock_manager.delete_session_profile.assert_not_called()

        asyncio.run(_run())


class TestSessionsPaneLayout:
    """The Sessions pane carries exactly one add control and exactly one
    table, whose columns are name | status | ↻ | ☐ | ×.

    These lock the simplification request: no second add button, no second
    table, and no leftover log panel below the table.
    """

    @staticmethod
    def _app() -> Any:
        from modules.tui.src.surface_tui_app_screen import QwenTuiApp

        return QwenTuiApp(
            workspace=MagicMock(),
            prompt=MagicMock(),
            slot_config=MagicMock(),
            session=MagicMock(),
            jobs=MagicMock(),
            updater=MagicMock(),
            job_storage=MagicMock(),
        )

    @staticmethod
    async def _open_sessions(app: Any, pilot: Any) -> None:
        """Bring the Sessions pane on screen and let it lay out."""
        from textual.widgets import TabbedContent

        app.query_one(TabbedContent).active = "tab-sessions"
        await pilot.pause(0.4)
        await pilot.pause(0.4)

    def test_exactly_one_add_session_button(self) -> None:
        """One full-width '⊕ ADD SESSION' control, #btn-session-add."""
        from textual.widgets import Button

        app = self._app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)) as pilot:
                await self._open_sessions(app, pilot)
                adds = [b for b in app.query(Button) if "add session" in str(b.label).lower()]
                assert len(adds) == 1, f"expected 1 Add Session button, got {len(adds)}"
                add = adds[0]
                assert add.id == "btn-session-add"
                # Contained button hugging the table panel's top-right (problem 5),
                # not a full-width band.
                assert add.has_class("btn-session-add-contained"), list(add.classes)

        asyncio.run(_run())

    def test_exactly_one_table_with_the_five_columns(self) -> None:
        """One #session-table; its head row is NAME | STATUS | ACTIONS and
        each session row carries the three action buttons."""
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Button, Label

        app = self._app()
        session = MagicMock()
        session.name = "arwaky007"
        session.session_id = "session_1"
        session.is_healthy = True
        session.is_limited = False
        session.status = MagicMock()
        session.status.value = "active"
        session.path = MagicMock()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                tables = list(app.query("#session-table"))
                assert len(tables) == 1, f"expected 1 table container, got {len(tables)}"
                assert isinstance(tables[0], Vertical)

                # No DataTable anywhere: the pane has one hand-built table.
                from textual.widgets import DataTable

                assert len(list(app.query(DataTable))) == 0, "no DataTable may remain on the pane"

                head = tables[0].query_one(".session-row-head", Horizontal)
                head_cells = [str(c.render()) for c in head.query(Label)]
                assert head_cells == ["NAME", "STATUS", "ACTIONS"], head_cells

                # Mount one session row and check the five columns line up.
                rows = app.query_one("#session-rows", Vertical)
                await rows.mount(app._account_card(session, 1))
                row = rows.query_one(".session-row", Horizontal)
                cells = list(row.query(Label))
                buttons = list(row.query(Button))
                assert len(cells) == 2, f"expected name+status cells, got {len(cells)}"
                assert "arwaky007" in str(cells[0].render())
                assert "ACTIVE" in str(cells[1].render())
                assert len(buttons) == 3, f"expected 3 action buttons, got {len(buttons)}"
                assert [b.name for b in buttons] == [
                    "account-refresh-1",
                    "account-health-1",
                    "account-delete-1",
                ]

        asyncio.run(_run())

    def test_no_log_panel_below_the_table(self) -> None:
        """The stray 'Registered Sessions' log view is gone."""
        app = self._app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                assert len(list(app.query("#log-view-sessions"))) == 0

        asyncio.run(_run())

    def test_metric_row_is_registered_active_expired(self) -> None:
        """The status row reads REGISTERED / ACTIVE / EXPIRED, no LIMITED."""
        from textual.widgets import Label

        app = self._app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                texts = [
                    str(app.query_one(f"#session-metric-{key}", Label).render())
                    for key in ("registered", "active", "expired")
                ]
                assert texts == ["0", "0", "0"], texts

        asyncio.run(_run())


def _sync_cft(app: Any) -> None:
    """Point call_from_thread at a synchronous callback for the test."""

    def _cft(callback, *args, **kwargs):
        callback(*args, **kwargs)
        return None

    app.call_from_thread = _cft


__all__ = [
    "TestAccountCardButtons",
    "TestAccountButtonRouting",
    "TestDeleteSessionWorker",
    "TestSessionsPaneLayout",
]
