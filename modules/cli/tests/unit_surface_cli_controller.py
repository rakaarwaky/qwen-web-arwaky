"""Extended tests for main.py — covering interactive controller, _run_manual_login, main()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from modules.cli.src.surface_cli_interactive_controller import InteractiveController
from modules.root_cli_main_entry import main


def _make_controller() -> InteractiveController:
    # AR-1: 3rd positional arg is prompt (IPromptAggregate), 4th is slot_config (IConfigAggregate)
    return InteractiveController(
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
    )


def _controller_with_rotator(response: object, *, raises: bool = False) -> InteractiveController:
    rotator = MagicMock()
    if raises:
        rotator.rotate = AsyncMock(side_effect=RuntimeError("rotation failed"))
    else:
        rotator.rotate = AsyncMock(return_value=response)
    return InteractiveController(MagicMock(), MagicMock(), MagicMock(), session_rotator=rotator)


def _rotator_response(path: Path | None) -> MagicMock:
    response = MagicMock()
    if path is None:
        response.session = None
    else:
        response.session = MagicMock(path=path)
    return response


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

    def test_headless_run_passes_a_session_resolver_function(self):
        """The headless path must hand ``dispatch_run`` a pool resolver.

        The pipeline builds its own AppConfig, so without the resolver the
        pool selection is dropped and an empty default session is used instead
        of a logged-in profile. The function (not its result) must be passed,
        so the pipeline can resolve on demand.
        """
        controller = _make_controller()
        with patch("modules.cli.src.surface_cli_run_command.dispatch_run") as dispatch:
            dispatch.return_value = {"success": True}
            controller.run(MagicMock(), prompt=False)

        resolver = dispatch.call_args.kwargs["session_resolver"]
        assert callable(resolver)
        # No rotator injected: the resolver reports no override.
        assert resolver() is None

    def test_headless_run_resolver_returns_the_rotated_pool_session(self):
        pool_path = Path("/home/user/.local/share/qwen-web-arwaky/sessions/arwaky007")
        controller = _controller_with_rotator(_rotator_response(pool_path))
        with patch("modules.cli.src.surface_cli_run_command.dispatch_run") as dispatch:
            dispatch.return_value = {"success": True}
            controller.run(MagicMock(), prompt=False)

        resolver = dispatch.call_args.kwargs["session_resolver"]
        assert resolver() == pool_path

    def test_headless_run_resolver_falls_back_to_none_without_a_pool_session(self):
        controller = _controller_with_rotator(_rotator_response(None))
        with patch("modules.cli.src.surface_cli_run_command.dispatch_run") as dispatch:
            dispatch.return_value = {"success": True}
            controller.run(MagicMock(), prompt=False)

        resolver = dispatch.call_args.kwargs["session_resolver"]
        assert resolver() is None

    def test_headless_run_resolver_survives_a_rotator_failure(self, capsys):
        controller = _controller_with_rotator(MagicMock(), raises=True)
        with patch("modules.cli.src.surface_cli_run_command.dispatch_run") as dispatch:
            dispatch.return_value = {"success": True}
            controller.run(MagicMock(), prompt=False)

        resolver = dispatch.call_args.kwargs["session_resolver"]
        assert resolver() is None
        captured = capsys.readouterr()
        assert "[WARN] Session rotation failed" in captured.err
        assert "falling back to the default session" in captured.err


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

        from modules.tui.src.surface_tui_app_screen import QwenTuiApp
        from modules.tui.src.surface_tui_component import QwenTuiLogHandler

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
