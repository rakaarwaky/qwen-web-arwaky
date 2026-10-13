"""Unit tests for the Sessions-pane account card action buttons.

The card foot carries two icon-only buttons:
- 🧪 (test, ``account-test-<n>``): runs the pool health check — the same
  probe as ``qwa session health`` (``SessionHealthChecker``).
- 🗑 (trash, ``account-delete-<n>``): removes the pool entry and deletes
  the Chromium profile — the same logic as ``qwa session remove``
  (``SessionManager.remove_session`` + ``delete_session_profile``),
  guarded by a ``ConfirmModal``.

These tests lock the button labels/names, the event routing, and the
delete wiring.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from unittest.mock import MagicMock, patch

from modules.tui.src.surface_tui_utils import _TuiUtilsMixin


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

        card = _TuiUtilsMixin._account_card(session, 1)

        # Textual only registers children with the widget tree once mounted,
        # so mount the card under a container in a live app before querying.
        from textual.containers import Container
        from textual.widgets import Button

        from modules.tui.src.surface_tui_app import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            direct=MagicMock(),
            file_only=MagicMock(),
            attachment=MagicMock(),
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
                # Two buttons: flask (⚗) and trash (🗑)
                assert len(buttons) == 2, f"expected 2 buttons, got {len(buttons)}"
                assert "🧪" in labels[0], f"first button should be the flask icon, got {labels!r}"
                assert "🗑" in labels[1], f"second button should be the trash icon, got {labels!r}"
                # Names ride on position so a re-check rebuild can't collide ids
                assert buttons[0].name == "account-test-1"
                assert buttons[1].name == "account-delete-1"

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

        from modules.tui.src.surface_tui_app import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            direct=MagicMock(),
            file_only=MagicMock(),
            attachment=MagicMock(),
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
        from modules.tui.src.surface_tui_app import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            direct=MagicMock(),
            file_only=MagicMock(),
            attachment=MagicMock(),
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
        from modules.tui.src.surface_tui_app import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            direct=MagicMock(),
            file_only=MagicMock(),
            attachment=MagicMock(),
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
                    app._account_button_pressed("test", 1)
                    mock_health.assert_called_once()

        asyncio.run(_run())


class TestDeleteSessionWorker:
    """_run_delete_session runs the same logic as 'qwa session remove':
    remove the pool entry, then delete the profile via the manager."""

    def test_delete_removes_pool_entry_and_profile(self) -> None:
        from modules.tui.src.surface_tui_app import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            direct=MagicMock(),
            file_only=MagicMock(),
            attachment=MagicMock(),
            slot_config=MagicMock(),
            session=MagicMock(),
            jobs=MagicMock(),
            updater=MagicMock(),
            job_storage=MagicMock(),
        )

        # Seed the sessions cache with one entry.
        session_info = MagicMock()
        session_info.name = "arwaky007"
        session_info.session_id = "session_1"
        session_info.path = MagicMock()
        app._sessions_cache = [session_info]
        app._last_delete_name = "arwaky007"

        mock_manager = MagicMock()
        mock_manager.remove_session.return_value = True
        app._session_manager = mock_manager

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                from textual.worker import WorkerFailed

                _sync_cft(app)
                worker = app._run_delete_session(True)
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()
                mock_manager.remove_session.assert_called_once_with("session_1")
                mock_manager.delete_session_profile.assert_called_once_with(session_info.path)

        asyncio.run(_run())

    def test_delete_declined_is_noop(self) -> None:
        from modules.tui.src.surface_tui_app import QwenTuiApp

        app = QwenTuiApp(
            workspace=MagicMock(),
            direct=MagicMock(),
            file_only=MagicMock(),
            attachment=MagicMock(),
            slot_config=MagicMock(),
            session=MagicMock(),
            jobs=MagicMock(),
            updater=MagicMock(),
            job_storage=MagicMock(),
        )
        mock_manager = MagicMock()
        app._session_manager = mock_manager

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                from textual.worker import WorkerFailed

                _sync_cft(app)
                worker = app._run_delete_session(False)
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()
                mock_manager.remove_session.assert_not_called()
                mock_manager.delete_session_profile.assert_not_called()

        asyncio.run(_run())


def _sync_cft(app: Any) -> None:
    """Patch call_from_thread so it invokes the callback synchronously."""

    def _cft(callback, *args, **kwargs):
        callback(*args, **kwargs)
        return None

    patch.object(app, "call_from_thread", _cft).start()


__all__ = [
    "TestAccountCardButtons",
    "TestAccountButtonRouting",
    "TestDeleteSessionWorker",
]
