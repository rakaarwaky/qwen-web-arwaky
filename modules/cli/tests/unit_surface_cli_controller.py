"""Extended tests for main.py — covering interactive controller, _run_manual_login, main()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_interactive_controller import InteractiveController
from modules.root_cli_main_entry import main


def _make_controller() -> InteractiveController:
    # AR-1: 5th positional arg is slot_config (ISlotRunPlanProtocol), now
    # injected from the Root container instead of being constructed in the Surface.
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

    def test_main_session_login_dispatches(self):
        with (
            patch("sys.argv", ["qwen-cli", "session", "login", "--name", "default"]),
            patch("modules.root_cli_main_entry.handle_sessions", return_value=0) as mock_sessions,
        ):
            result = main()
            assert result == 0
            mock_sessions.assert_called_once()


class TestQwenTuiLogHandler:
    def test_emit_info_and_error_levels(self):
        import logging

        from modules.tui.src.surface_tui_app import QwenTuiApp
        from modules.tui.src.surface_tui_components import QwenTuiLogHandler

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
