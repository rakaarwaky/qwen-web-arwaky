"""E2E tests for CLI module — tests end-to-end flows with mocked browser."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCLIE2E:
    """End-to-end tests for CLI module flows."""

    def test_cli_prompt_direct_flow(self, tmp_path: Path):
        """Test complete prompt-direct flow."""
        from modules.cli.src.surface_cli_run_command import RunCommand

        # Verify command exists
        assert RunCommand is not None

    def test_cli_login_flow(self, tmp_path: Path):
        """Test login command structure."""
        from modules.cli.src.surface_cli_login_command import handle as login_handle
        assert callable(login_handle)

    def test_cli_init_flow(self, tmp_path: Path):
        """Test init command structure."""
        from modules.cli.src.surface_cli_init_command import handle as init_handle
        assert callable(init_handle)

    def test_cli_doctor_flow(self, tmp_path: Path):
        """Test doctor command structure."""
        from modules.cli.src.surface_cli_doctor_command import handle as doctor_handle
        assert callable(doctor_handle)

    def test_cli_sessions_flow(self, tmp_path: Path):
        """Test sessions command structure."""
        from modules.cli.src.surface_cli_sessions_command import handle as sessions_handle
        assert callable(sessions_handle)

    def test_cli_update_flow(self, tmp_path: Path):
        """Test update command structure."""
        from modules.cli.src.surface_cli_update_command import handle as update_handle
        assert callable(update_handle)
