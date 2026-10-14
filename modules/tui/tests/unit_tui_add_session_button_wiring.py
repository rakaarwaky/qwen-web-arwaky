"""Regression test for the ADD SESSION button wiring.

The full-width "+ ADD SESSION" button on the Sessions tab must open the
name dialog (``AddSessionModal``) and then run the headed browser login
for the typed name — the same flow the ``a`` / ``session_add_new`` binding
uses. It must not fall back to the legacy ``SessionSetupScreen`` flow,
which never asks for a name.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from modules.tui.src.surface_tui_app import QwenTuiApp


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

    def test_add_session_button_does_not_use_legacy_flow(self) -> None:
        """The button must not fall back to ``_session_login_action``."""

        async def _run() -> None:
            app = _make_app()
            async with app.run_test(size=(150, 44)):
                with (
                    patch.object(app, "action_session_add_new") as mock_action,
                    patch.object(app, "_session_login_action") as mock_legacy,
                ):
                    app.on_button_pressed(_ButtonEvent("btn-session-add"))
                    mock_action.assert_called_once()
                    mock_legacy.assert_not_called()

        asyncio.run(_run())
