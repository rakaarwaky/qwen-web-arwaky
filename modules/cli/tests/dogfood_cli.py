"""Dogfood tests for CLI module — structure validation only, no live API calls.

These tests verify the CLI structure is intact:
1. All commands can be imported
2. Help output is valid
3. No circular import issues
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str]) -> tuple[int, str]:
    """Run CLI command and return result."""
    root = Path(__file__).resolve().parent.parent.parent.parent
    env = dict(__import__('os').environ)
    env["PYTHONPATH"] = str(root)
    result = subprocess.run(
        [sys.executable, "-m", "modules.root_cli_main_entry"] + args,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return result.returncode, result.stdout


class TestCLIDogfood:
    """Test that CLI module components can be imported and instantiated."""

    def test_import_all_surface_commands(self):
        """All surface CLI commands must be importable."""
        from modules.cli.src import surface_cli_doctor_command
        from modules.cli.src import surface_cli_init_command
        from modules.cli.src import surface_cli_login_command
        from modules.cli.src import surface_cli_run_command
        from modules.cli.src import surface_cli_sessions_command
        from modules.cli.src import surface_cli_update_command
        assert all([surface_cli_doctor_command, surface_cli_init_command,
                    surface_cli_login_command, surface_cli_run_command])

    def test_import_tui_modules(self):
        """All TUI modules must be importable."""
        from modules.cli.src import surface_cli_tui_app
        from modules.cli.src import surface_cli_tui_components
        from modules.cli.src import surface_cli_tui_handlers
        from modules.cli.src import surface_cli_tui_workers
        assert surface_cli_tui_app is not None

    def test_cli_commands_registered(self):
        """All CLI commands should appear in help output."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        expected_commands = ["prompt-direct", "prompt-only", "prompt-with-attachment",
                           "login", "init", "sessions", "doctor", "update"]
        for cmd in expected_commands:
            assert cmd in stdout, f"Command '{cmd}' not found in help output"

    def test_mcp_help(self):
        """MCP server help should be available."""
        from modules.root_mcp_main_entry import main, run_mcp_server
        assert callable(run_mcp_server)

    def test_cli_module_structure(self):
        """CLI module structure should be valid."""
        import modules.cli.src
        assert hasattr(modules.cli.src, "__path__")
