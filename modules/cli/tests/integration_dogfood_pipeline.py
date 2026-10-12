"""Dogfood pipeline tests — structure validation for CLI commands.

These tests verify the CLI command structure and help output:
1. The `prompt` group exists with direct/file/attach subcommands
2. The `session` and `job` groups exist

NEVER RUNS API CALLS — structure tests only.
Real API validation: run pytest --run-dogfood with live Qwen session.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run CLI command and return result."""
    return subprocess.run(
        [sys.executable, "-m", "modules.root_cli_main_entry"] + args,
        capture_output=True,
        text=True,
    )


class TestPipelineStructure:
    """Test that all pipeline entry points are discoverable."""

    @pytest.mark.parametrize("group", ["prompt", "session", "job"])
    def test_command_group_exists(self, group: str):
        """Verify each pipeline command group is registered."""
        result = _run_cli(["--help"])
        assert result.returncode == 0
        assert group in result.stdout

    def test_prompt_subcommands_exist(self):
        """Verify the prompt direct/file/attach subcommands are registered."""
        result = _run_cli(["prompt", "--help"])
        assert result.returncode == 0
        for subcommand in ("direct", "file", "attach"):
            assert subcommand in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
