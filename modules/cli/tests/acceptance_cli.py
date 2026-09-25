"""Acceptance tests for CLI module — verifies business requirements are met."""

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


class TestCLIAcceptance:
    """Acceptance tests mapping to business requirements."""

    def test_cli_main_entry_point(self):
        """FRD-010: CLI must have a working entry point."""
        from modules.root_cli_main_entry import main
        assert callable(main)

    def test_mcp_main_entry_point(self):
        """FRD-011: MCP server must have a working entry point."""
        from modules.root_mcp_main_entry import main, run_mcp_server
        assert callable(main)
        assert callable(run_mcp_server)

    def test_prompt_direct_command_registered(self):
        """FRD-012: prompt-direct command must be registered."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        assert "prompt-direct" in stdout

    def test_prompt_only_command_registered(self):
        """FRD-013: prompt-only command must be registered."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        assert "prompt-only" in stdout

    def test_prompt_with_attachment_command_registered(self):
        """FRD-014: prompt-with-attachment command must be registered."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        assert "prompt-with-attachment" in stdout

    def test_login_command_registered(self):
        """FRD-015: login command must be registered."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        assert "login" in stdout

    def test_tui_interface_exists(self):
        """FRD-016: TUI interface must exist and be importable."""
        from modules.cli.src.surface_cli_tui_app import TuiApp
        assert TuiApp is not None

    def test_cli_all_commands_listed_in_help(self):
        """FRD-017: All commands must appear in help output."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        commands = ["prompt-direct", "prompt-only", "prompt-with-attachment",
                   "login", "init", "sessions", "doctor", "update"]
        for cmd in commands:
            assert cmd in stdout, f"Command '{cmd}' missing from help"
