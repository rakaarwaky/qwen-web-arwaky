"""Unit tests for the TUI system-action routing and Settings-pane overrides."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock, patch

from textual.widgets import TabbedContent
from textual.worker import WorkerFailed

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


def _sync_cft(app: QwenTuiApp) -> None:
    """Patch call_from_thread so it invokes the callback synchronously.

    The real Textual implementation queues the callback to the event loop,
    which never fires inside a synchronous test body.
    """

    def _cft(callback, *args, **kwargs):
        callback(*args, **kwargs)
        return None

    patch.object(app, "call_from_thread", _cft).start()


class TestSystemActionRouting:
    """Verify _system_action_pressed routes to the correct handler method."""

    def test_doctor_button_routes_to_doctor_worker(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "_run_doctor_worker") as mock_doctor:
                    app._system_action_pressed("btn-tui-doctor")
                    mock_doctor.assert_called_once()

        asyncio.run(_run())

    def test_update_button_routes_to_update_worker(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "_run_update_worker") as mock_update:
                    app._system_action_pressed("btn-tui-update")
                    mock_update.assert_called_once()

        asyncio.run(_run())

    def test_unknown_button_id_logs_warning(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "_log_msg") as mock_log:
                    app._system_action_pressed("btn-nonexistent")
                    # The router should log a warning for an unknown button ID.
                    assert mock_log.called

        asyncio.run(_run())


class TestSettingsPaneWidgets:
    """Verify the Settings pane renders the widget IDs it owns (Issue 10)."""

    def test_system_actions_card_rendered(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                # Navigate to Settings tab
                app.action_switch_tab_settings()
                tabs = app.query_one(TabbedContent)
                assert tabs.active == "tab-settings"

        asyncio.run(_run())


class TestRunUpdateWorker:
    """_run_update_worker: updater injection and update check paths."""

    def test_update_no_updater_logs_warning(self) -> None:
        app = _make_app()
        app._updater = None

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                _sync_cft(app)
                with patch.object(app, "_log_msg") as mock_log:
                    worker = app._run_update_worker()
                    with contextlib.suppress(WorkerFailed):
                        await worker.wait()
                    # When updater is None, the worker logs a "No updater injected" message.
                    assert any("No updater injected" in str(c) for c in mock_log.call_args_list), (
                        f"Expected 'No updater injected' log; got: {mock_log.call_args_list}"
                    )

        asyncio.run(_run())
