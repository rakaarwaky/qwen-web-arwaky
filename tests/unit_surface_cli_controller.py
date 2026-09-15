"""Extended tests for main.py — covering interactive controller, _run_manual_login, main()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_interactive_controller import InteractiveController
from modules.root_cli_main_entry import main
from modules.shared.src import AppConfig


def _make_controller() -> InteractiveController:
    return InteractiveController(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())


class TestInteractiveControllerRun:
    def test_non_tty_returns_validation_error(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = _make_controller().run()
        assert result["success"] is False
        assert result["category"] == "validation_error"
        assert result["ref"] == "cli-400"

    def test_explicit_exit_returns_success(self):
        result = _make_controller().run(cfg=None, prompt=False)
        assert result == {"success": True, "message": "Exited."}


class TestRunManualLogin:
    def test_not_tty_exits(self):
        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "modules.cli.src.surface_cli_login_command.handle",
                return_value={"success": False, "error": "TTY required"},
            ) as mock_handle,
        ):
            mock_stdin.isatty.return_value = False
            cfg = AppConfig(
                mode="login",
                input_path=Path("/tmp/in"),
                output_path=Path("/tmp/out"),
                done_path=Path("/tmp/done"),
                failed_path=Path("/tmp/failed"),
                proc_path=Path("/tmp/proc"),
                session_path=Path("/tmp/session"),
            )
            from modules.root_cli_main_entry import _run_manual_login

            result = _run_manual_login(cfg)
            mock_handle.assert_called_once()
            assert result == 1

    def test_login_opens_browser(self):
        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "modules.cli.src.surface_cli_login_command.handle", return_value={"success": True, "message": "ok"}
            ) as mock_handle,
        ):
            mock_stdin.isatty.return_value = True
            cfg = AppConfig(
                mode="login",
                input_path=Path("/tmp/in"),
                output_path=Path("/tmp/out"),
                done_path=Path("/tmp/done"),
                failed_path=Path("/tmp/failed"),
                proc_path=Path("/tmp/proc"),
                session_path=Path("/tmp/session"),
            )
            from modules.root_cli_main_entry import _run_manual_login

            result = _run_manual_login(cfg)
            mock_handle.assert_called_once()
            assert result == 0

    def test_failure_prints_error_to_stderr(self, capsys):
        with patch(
            "modules.cli.src.surface_cli_login_command.handle",
            return_value={"success": False, "error": "Manual login requires an interactive terminal (TTY)"},
        ):
            cfg = AppConfig(
                mode="login",
                input_path=Path("/tmp/in"),
                output_path=Path("/tmp/out"),
                done_path=Path("/tmp/done"),
                failed_path=Path("/tmp/failed"),
                proc_path=Path("/tmp/proc"),
                session_path=Path("/tmp/session"),
            )
            from modules.root_cli_main_entry import _run_manual_login

            result = _run_manual_login(cfg)
            captured = capsys.readouterr()
            assert "Manual login requires an interactive terminal (TTY)" in captured.err
            assert result == 1


class TestMain:
    def test_main_interactive_exit(self):
        with (
            patch("sys.argv", ["qwen-cli"]),
            patch("sys.stdin.isatty", return_value=True),
            patch(
                "modules.cli.src.surface_cli_interactive_controller.InteractiveController.run",
                return_value={"success": True, "message": "Exited."},
            ) as mock_run,
        ):
            result = main()
            assert result == 0
            mock_run.assert_called_once()

    def test_main_non_tty_interactive_fails(self, capsys):
        with patch("sys.argv", ["qwen-cli"]), patch("sys.stdin.isatty", return_value=False):
            result = main()
            captured = capsys.readouterr()
            assert result == 1
            assert "Interactive TUI mode requires a terminal (TTY)" in captured.err

    def test_main_login_mode(self):
        with (
            patch("sys.argv", ["qwen-cli", "login"]),
            patch("modules.root_cli_main_entry._run_manual_login", return_value=0),
        ):
            result = main()
            assert result == 0


class TestQwenTuiLogHandler:
    def test_emit_info_and_error_levels(self):
        import logging

        from modules.cli.src.surface_cli_tui_app import QwenTuiApp
        from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler

        mock_app = MagicMock(spec=QwenTuiApp)
        handler = QwenTuiLogHandler(mock_app)

        info_rec = logging.LogRecord("test_logger", logging.INFO, "path/to/file", 10, "Test info message", (), None)
        handler.emit(info_rec)
        assert mock_app.call_from_thread.called
        call_args = mock_app.call_from_thread.call_args[0]
        assert "Test info message" in call_args[1]

        mock_app.reset_mock()
        err_rec = logging.LogRecord("test_logger", logging.ERROR, "path/to/file", 20, "Test error message", (), None)
        handler.emit(err_rec)
        assert mock_app.call_from_thread.called
        call_args = mock_app.call_from_thread.call_args[0]
        assert "Test error message" in call_args[1]
        assert "ERROR" in call_args[1]

    def test_on_mount_and_unmount_hooks_handler(self):
        import logging

        from modules.cli.src.surface_cli_tui_app import QwenTuiApp
        from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler

        app = QwenTuiApp(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        with patch.object(app, "query_one") as mock_query, patch.object(app, "set_timer"):
            mock_log = MagicMock()
            mock_query.return_value = mock_log
            app._deferred_startup()

            root_logger = logging.getLogger()
            assert any(isinstance(h, QwenTuiLogHandler) for h in root_logger.handlers)

            app.on_unmount()
            assert not any(isinstance(h, QwenTuiLogHandler) for h in root_logger.handlers)


def test_doctor_command(capsys):
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    code = run_doctor(json_output=False)
    captured = capsys.readouterr()
    assert code in (0, 1)
    assert "System Health Diagnostic" in captured.out
    assert "Python Version" in captured.out


def test_doctor_command_json(capsys):
    import json

    from modules.cli.src.surface_cli_doctor_command import run_doctor

    code = run_doctor(json_output=True)
    captured = capsys.readouterr()
    assert code in (0, 1)
    data = json.loads(captured.out)
    assert data["status"] in ("healthy", "unhealthy")
    assert len(data["checks"]) >= 5
