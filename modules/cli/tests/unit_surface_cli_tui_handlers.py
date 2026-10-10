"""Unit tests for the Settings-pane system-action handlers in surface_cli_tui_handlers."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock, patch

from textual.widgets import Button, DataTable, TabbedContent
from textual.worker import WorkerFailed

from modules.cli.src.surface_cli_tui_app import QwenTuiApp
from modules.cli.src.surface_cli_tui_compose import JOBS_TABLE_ID
from modules.cli.src.surface_cli_tui_handlers import _noop


def _make_app() -> QwenTuiApp:
    return QwenTuiApp(
        workspace=MagicMock(),
        direct=MagicMock(),
        file_only=MagicMock(),
        attachment=MagicMock(),
        slot_config=MagicMock(),
        setup=MagicMock(),
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

    def test_jobs_cleanup_button_routes_to_cleanup(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "_run_jobs_cleanup") as mock_cleanup:
                    app._system_action_pressed("btn-tui-jobs-cleanup")
                    mock_cleanup.assert_called_once()

        asyncio.run(_run())

    def test_jobs_refresh_button_routes_to_refresh(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "_refresh_jobs_table") as mock_refresh:
                    app._system_action_pressed("btn-jobs-refresh")
                    mock_refresh.assert_called_once()

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


class TestNoopFunction:
    def test_noop_callable_with_no_args(self) -> None:
        # _noop is used as a router fallback; call it directly to verify
        # it is a callable that takes no arguments.
        callable = _noop
        callable()


class TestRunJobsCleanup:
    """_run_jobs_cleanup: notify path when job_storage is absent or present."""

    def test_cleanup_notifies_warning_when_storage_absent(self) -> None:
        app = _make_app()
        app._job_storage = None

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                _sync_cft(app)
                with patch.object(app, "notify") as mock_notify:
                    worker = app._run_jobs_cleanup()
                    with contextlib.suppress(WorkerFailed):
                        await worker.wait()
                    mock_notify.assert_called_once()
                    args = mock_notify.call_args[0]
                    assert "Job storage not available" in args[0]

        asyncio.run(_run())

    def test_cleanup_reports_removed_count(self) -> None:
        app = _make_app()
        app._job_storage = MagicMock()
        app._job_storage.cleanup_stale_jobs.return_value = 3

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                _sync_cft(app)
                with patch.object(app, "notify") as mock_notify:
                    worker = app._run_jobs_cleanup()
                    with contextlib.suppress(WorkerFailed):
                        await worker.wait()
                    mock_notify.assert_called_once()
                    args = mock_notify.call_args[0]
                    assert "3 stale" in args[0]
                    assert "Running jobs are preserved" in args[0]

        asyncio.run(_run())

    def test_cleanup_zero_removed_shows_zero(self) -> None:
        app = _make_app()
        app._job_storage = MagicMock()
        app._job_storage.cleanup_stale_jobs.return_value = 0

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                _sync_cft(app)
                with patch.object(app, "notify") as mock_notify:
                    worker = app._run_jobs_cleanup()
                    with contextlib.suppress(WorkerFailed):
                        await worker.wait()
                    args = mock_notify.call_args[0]
                    assert "0 stale" in args[0]
                    assert "Running jobs are preserved" in args[0]

        asyncio.run(_run())

    def test_cleanup_error_notifies_error_severity(self) -> None:
        app = _make_app()
        app._job_storage = MagicMock()
        app._job_storage.cleanup_stale_jobs.side_effect = OSError("disk full")

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                _sync_cft(app)
                with patch.object(app, "notify") as mock_notify:
                    worker = app._run_jobs_cleanup()
                    with contextlib.suppress(WorkerFailed):
                        await worker.wait()
                    args, kwargs = mock_notify.call_args
                    assert kwargs.get("severity") == "error"
                    assert "disk full" in args[0]

        asyncio.run(_run())


class TestRefreshJobsTable:
    """_refresh_jobs_table / _refresh_jobs_table_worker: guard and worker logic."""

    def test_refresh_warns_when_jobs_aggregate_absent(self) -> None:
        app = _make_app()
        app._jobs = None

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "notify") as mock_notify:
                    app._refresh_jobs_table()
                    mock_notify.assert_called_once()
                    # The message is passed as a positional argument.
                    msg = mock_notify.call_args[0][0]
                    assert "Jobs aggregate not available" in msg

        asyncio.run(_run())

    def test_refresh_triggers_worker_when_jobs_present(self) -> None:
        app = _make_app()
        app._jobs = MagicMock()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                with patch.object(app, "_refresh_jobs_table_worker") as mock_worker:
                    app._refresh_jobs_table()
                    mock_worker.assert_called_once()

        asyncio.run(_run())

    def test_worker_error_logs_jobs_load_error(self) -> None:
        """_refresh_jobs_table_worker logs JOBS LOAD ERROR when the aggregate raises (Issue 37)."""
        app = _make_app()
        app._jobs = MagicMock()
        app._jobs.execute.side_effect = RuntimeError("storage down")

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                _sync_cft(app)
                with patch.object(app, "_log_msg") as mock_log:
                    worker = app._refresh_jobs_table_worker()
                    with contextlib.suppress(WorkerFailed):
                        await worker.wait()
                    # call_from_thread was patched to run the callback synchronously,
                    # so _log_msg was called in this thread and can be asserted here.
                    assert any("JOBS LOAD ERROR" in str(c) for c in mock_log.call_args_list), (
                        f"Expected JOBS LOAD ERROR log; got: {mock_log.call_args_list}"
                    )

        asyncio.run(_run())


class TestSettingsPaneWidgets:
    """Verify the Settings pane renders the new widget IDs (Issue 10)."""

    def test_system_actions_card_rendered(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                # Navigate to Settings tab
                app.action_switch_tab_settings()
                tabs = app.query_one(TabbedContent)
                assert tabs.active == "tab-settings"

                # All four new button IDs must be present
                for btn_id in ("btn-tui-doctor", "btn-tui-update", "btn-tui-jobs-cleanup", "btn-jobs-refresh"):
                    assert app.query_one(f"#{btn_id}", Button) is not None, btn_id

                # Jobs table must be present
                assert app.query_one(f"#{JOBS_TABLE_ID}", DataTable) is not None

        asyncio.run(_run())

    def test_jobs_table_rendered_in_settings_pane(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(150, 44)):
                app.action_switch_tab_settings()
                table = app.query_one(f"#{JOBS_TABLE_ID}", DataTable)
                assert table is not None
                # The DataTable starts empty (no rows until refreshed)
                assert table.row_count == 0

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
