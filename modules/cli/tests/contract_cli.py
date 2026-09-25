"""Contract tests for CLI module — verifies protocol/aggregate implementations."""

from __future__ import annotations

import pytest


class TestCLIContracts:
    """Verify CLI module contract implementations exist and are valid."""

    def test_tui_app_exists(self):
        from modules.cli.src.surface_cli_tui_app import QwenTuiApp
        assert QwenTuiApp is not None

    def test_login_handler_exists(self):
        from modules.cli.src.surface_cli_login_command import handle as login_handle
        assert callable(login_handle)

    def test_run_handler_exists(self):
        from modules.cli.src.surface_cli_run_command import dispatch_run
        assert callable(dispatch_run)

    def test_init_handler_exists(self):
        from modules.cli.src.surface_cli_init_command import handle as init_handle
        assert callable(init_handle)

    def test_doctor_handler_exists(self):
        from modules.cli.src.surface_cli_doctor_command import handle as doctor_handle
        assert callable(doctor_handle)

    def test_sessions_handler_exists(self):
        from modules.cli.src.surface_cli_sessions_command import handle as sessions_handle
        assert callable(sessions_handle)

    def test_update_handler_exists(self):
        from modules.cli.src.surface_cli_update_command import handle as update_handle
        assert callable(update_handle)

    def test_controller_exists(self):
        from modules.cli.src.surface_cli_interactive_controller import InteractiveController
        assert InteractiveController is not None
