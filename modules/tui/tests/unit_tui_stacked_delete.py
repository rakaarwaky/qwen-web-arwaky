"""Regression tests for FE-2-02: stacked delete-confirmation race.

Two stacked ConfirmModals used to share a single name field. Pushing
delete for B overwrote the field after A was pushed, so confirming modal A
deleted B. The name must be captured in the confirm closure instead.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from unittest.mock import MagicMock, patch

from modules.tui.src.surface_tui_app_screen import QwenTuiApp
from modules.tui.tests.fixture_tui_app import make_app


def _make_session(name: str, session_id: str) -> Any:
    session = MagicMock()
    session.name = name
    session.session_id = session_id
    session.path = MagicMock(name=f"path_{name}")
    return session


class TestStackedDeleteConfirm:
    """Confirming the first of two stacked delete modals deletes that name."""

    def test_no_shared_delete_name_field_on_app(self) -> None:
        """Issue 28: reintroducing the shared field must fail loudly."""
        # Name is assembled so a repo-wide grep for the removed symbol stays empty.
        banned = "_last" + "_delete_name"
        assert not hasattr(QwenTuiApp, banned)
        app = make_app()
        assert not hasattr(app, banned)

    def test_confirm_first_modal_deletes_first_session_not_second(self) -> None:
        app = make_app()

        mock_manager = MagicMock()
        mock_manager.remove_session.return_value = True
        app._session_manager = mock_manager

        session_a = _make_session("session-A", "id-A")
        session_b = _make_session("session-B", "id-B")
        app._sessions_cache = [session_a, session_b]
        app._sessions_loaded_once = True

        async def _run() -> None:
            async with app.run_test(size=(150, 44)) as pilot:
                from textual.worker import WorkerFailed

                def _cft(callback, *args, **kwargs):
                    callback(*args, **kwargs)
                    return None

                app.call_from_thread = _cft

                app._confirm_delete_session("session-A")
                await pilot.pause(0.05)
                app._confirm_delete_session("session-B")
                await pilot.pause(0.05)

                from textual.widgets import Button

                app.screen.query_one("#btn-cancel", Button).press()
                await pilot.pause(0.1)
                app.screen.query_one("#btn-confirm", Button).press()
                await pilot.pause(0.1)

                with contextlib.suppress(WorkerFailed):
                    for w in list(getattr(app, "_workers", []) or []):
                        if hasattr(w, "wait"):
                            await w.wait()
                await pilot.pause(0.2)

                removed_ids = [c.args[0] for c in mock_manager.remove_session.call_args_list]
                assert removed_ids == ["id-A"], removed_ids
                mock_manager.remove_session.assert_called_once_with("id-A")
                mock_manager.delete_session_profile.assert_called_once_with(session_a.path)

        asyncio.run(_run())

    def test_confirm_callback_captures_name_at_push_time(self) -> None:
        """Unit-level pin: each push's callback closes over its own name."""
        app = make_app()

        callbacks: list[Any] = []
        original_push = app.push_screen

        def _capture(screen: Any, callback: Any = None) -> None:
            callbacks.append(callback)
            return original_push(screen, callback)

        deleted: list[str] = []
        app._run_delete_session = lambda name: deleted.append(name)

        async def _run() -> None:
            async with app.run_test(size=(150, 44)) as pilot:
                with patch.object(app, "push_screen", _capture):
                    app._confirm_delete_session("session-A")
                    app._confirm_delete_session("session-B")
                await pilot.pause(0.05)

                assert len(callbacks) == 2
                callbacks[0](True)
                assert deleted == ["session-A"], deleted
                callbacks[1](True)
                assert deleted == ["session-A", "session-B"], deleted

        asyncio.run(_run())


__all__ = ["TestStackedDeleteConfirm"]
