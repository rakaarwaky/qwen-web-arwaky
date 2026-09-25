"""Smoke tests for CLI module — fast verification that CLI components work."""

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


class TestCLISmoke:
    """Fast smoke tests for CLI module (must complete in <5s)."""

    def test_cli_help(self):
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        assert "qwen-web-arwaky" in stdout

    def test_cli_prompt_direct_help(self):
        returncode, stdout = _run_cli(["prompt-direct", "--help"])
        assert returncode == 0

    def test_cli_prompt_only_help(self):
        returncode, stdout = _run_cli(["prompt-only", "--help"])
        assert returncode == 0

    def test_cli_login_help(self):
        returncode, stdout = _run_cli(["login", "--help"])
        assert returncode == 0

    def test_cli_init_help(self):
        returncode, stdout = _run_cli(["init", "--help"])
        assert returncode == 0

    def test_mcp_entry_importable(self):
        from modules.root_mcp_main_entry import main, run_mcp_server
        assert callable(main)
        assert callable(run_mcp_server)
