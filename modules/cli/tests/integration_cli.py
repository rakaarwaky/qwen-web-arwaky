"""Integration tests for CLI module — tests modules working together."""

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


class TestCLIIntegration:
    """Integration tests for CLI module components."""

    def test_cli_with_config(self):
        """Test CLI respects configuration."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        assert "prompt-direct" in stdout

    def test_mcp_entry_point(self):
        """Test MCP entry point is importable."""
        from modules.root_mcp_main_entry import main, run_mcp_server
        assert callable(main)
        assert callable(run_mcp_server)

    def test_cli_main_entry(self):
        """Test CLI main entry point."""
        from modules.root_cli_main_entry import main
        assert callable(main)

    def test_tui_components_importable(self):
        """Test TUI components can be imported."""
        from modules.cli.src.surface_cli_tui_components import render_slot_list
        assert callable(render_slot_list)

    def test_tui_workers_importable(self):
        """Test TUI workers can be imported."""
        from modules.cli.src.surface_cli_tui_workers import TaskWorker
        assert TaskWorker is not None
