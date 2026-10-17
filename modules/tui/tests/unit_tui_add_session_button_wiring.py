"""Regression test for the ADD SESSION button wiring.

The full-width "+ ADD SESSION" button on the Sessions tab must open the
name dialog (``AddSessionModal``) and then run the headed browser login
for the typed name — the same flow the ``a`` / ``session_add_new`` binding
uses. The legacy ``SessionSetupScreen`` flow (which never asked for a
name) has been removed entirely.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from modules.tui.src.surface_tui_app_screen import QwenTuiApp


def _make_app() -> QwenTuiApp:
    return QwenTuiApp(
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


class _ButtonEvent:
    """Minimal stand-in for ``Button.Pressed`` carrying only the id."""

    def __init__(self, button_id: str) -> None:
        self.button = _Button(button_id)


class _Button:
    def __init__(self, button_id: str) -> None:
        self.id = button_id
        self.name = None


class TestAddSessionButtonWiring:
    """The ADD SESSION button routes to the name dialog, not the legacy flow."""

    def test_add_session_button_pushes_name_dialog(self) -> None:
        """Pressing ``btn-session-add`` calls ``action_session_add_new``."""

        async def _run() -> None:
            app = _make_app()
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "action_session_add_new") as mock_action:
                    app.on_button_pressed(_ButtonEvent("btn-session-add"))
                    mock_action.assert_called_once()

        asyncio.run(_run())

    def test_action_login_action_opens_name_dialog(self) -> None:
        """The ctrl+l login binding routes to the name dialog too."""

        async def _run() -> None:
            app = _make_app()
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "action_session_add_new") as mock_action:
                    app.action_login_action()
                    mock_action.assert_called_once()

        asyncio.run(_run())

    def test_legacy_session_setup_screen_is_removed(self) -> None:
        """``SessionSetupScreen`` and its module are gone for good."""
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("modules.tui.src.surface_tui_session_setup")
