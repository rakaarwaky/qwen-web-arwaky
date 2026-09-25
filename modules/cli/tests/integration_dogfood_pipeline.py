"""Dogfood pipeline tests — structure validation for CLI commands.

These tests verify the CLI command structure and help output:
1. prompt-direct command exists
2. prompt-only command exists
3. prompt-with-attachment command exists

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

    def test_prompt_direct_exists(self):
        """Verify prompt-direct command is registered."""
        result = _run_cli(["--help"])
        assert result.returncode == 0
        assert "prompt-direct" in result.stdout

    def test_prompt_only_exists(self):
        """Verify prompt-only command is registered."""
        result = _run_cli(["--help"])
        assert result.returncode == 0
        assert "prompt-only" in result.stdout

    def test_prompt_with_attachment_exists(self):
        """Verify prompt-with-attachment command is registered."""
        result = _run_cli(["--help"])
        assert result.returncode == 0
        assert "prompt-with-attachment" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
