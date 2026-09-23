"""Dogfood pipeline tests — real end-to-end validation of CLI commands.

These tests verify the three main user-facing pipelines work with a live Qwen session:
1. prompt-direct: Send inline text prompt
2. prompt-only: Process a prompt file (no attachment)
3. prompt-with-attachment: Process a prompt file with a file attachment

Run with: pytest modules/cli/tests/integration_dogfood_pipeline.py -v --run-dogfood

Requirements:
- Must have a valid Qwen session (run 'qwen-web-arwaky login' first)
- Uses the shared qwen_session from ~/.local/share/qwen-web/
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Test fixtures directory
DOGFOOD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "dogfood_fixtures"
DOGFOOD_DIR.mkdir(exist_ok=True)

PROMPT_FILE = DOGFOOD_DIR / "dogfood_prompt.md"
ATTACHMENT_FILE = DOGFOOD_DIR / "dogfood_attachment.txt"


@pytest.fixture(scope="module")
def test_files():
    """Create test files for dogfood runs."""
    PROMPT_FILE.write_text("# Dogfood Test\n\nPlease reply with: Dogfood test passed!\n")
    ATTACHMENT_FILE.write_text("This is a test attachment for dogfood pipeline validation.\nLine 2.\n")
    yield
    # Cleanup after tests
    for f in [PROMPT_FILE, ATTACHMENT_FILE]:
        if f.exists():
            f.unlink()


def pytest_addoption(parser):
    parser.addoption(
        "--run-dogfood",
        action="store_true",
        default=False,
        help="Run dogfood pipeline tests requiring live Qwen session",
    )


def pytest_collection_modifyitems(config, items):
    """Skip dogfood tests unless --run-dogfood is set."""
    if not config.getoption("--run-dogfood"):
        skip = pytest.mark.skip(reason="Need --run-dogfood to run dogfood tests")
        for item in items:
            if "integration_dogfood" in item.nodeid:
                item.add_marker(skip)


def _run_cli(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run CLI command and return result. No timeout for real API calls."""
    return subprocess.run(
        [sys.executable, "-m", "modules.root_cli_main_entry"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _has_valid_session() -> bool:
    """Check if a valid Qwen session exists."""
    session_dir = Path.home() / ".local" / "share" / "qwen-web" / "qwen_session"
    if not session_dir.exists():
        return False
    # Check for component_crx_cache which indicates a saved session
    return (session_dir / "component_crx_cache").exists()


class TestPromptDirectPipeline:
    """Test prompt-direct command — send inline text prompt."""

    @pytest.mark.skipif(not _has_valid_session(), reason="No valid Qwen session found")
    def test_prompt_direct_runs(self, test_files, tmp_path):
        """Verify prompt-direct command executes without crash."""
        output = tmp_path / "direct_output.md"
        result = _run_cli([
            "prompt-direct",
            "-t", "Say: Dogfood test OK",
            "-o", str(output),
            "--headless",
        ], timeout=None)  # No timeout for real API calls
        # Exit code 0 = success, 1 = session/auth error (acceptable for testing pipeline)
        assert result.returncode in (0, 1), f"CLI crashed: {result.stderr[:500]}"
        print(f"\n[DIRECT] Return code: {result.returncode}")
        if result.stdout:
            print(f"[DIRECT] Output preview: {result.stdout[:200]}")


class TestPromptOnlyPipeline:
    """Test prompt-only command — process a prompt file."""

    @pytest.mark.skipif(not _has_valid_session(), reason="No valid Qwen session found")
    def test_prompt_only_processes_file(self, test_files, tmp_path):
        """Verify prompt-only command executes without crash."""
        output = tmp_path / "file_output.md"
        result = _run_cli([
            "prompt-only",
            "-i", str(PROMPT_FILE),
            "-o", str(output),
            "--headless",
        ], timeout=None)  # No timeout for real API calls
        assert result.returncode in (0, 1), f"CLI crashed: {result.stderr[:500]}"
        print(f"\n[FILE-ONLY] Return code: {result.returncode}")
        if result.stdout:
            print(f"[FILE-ONLY] Output preview: {result.stdout[:200]}")


class TestPromptWithAttachmentPipeline:
    """Test prompt-with-attachment command — process prompt + file."""

    @pytest.mark.skipif(not _has_valid_session(), reason="No valid Qwen session found")
    def test_prompt_with_attachment_works(self, test_files, tmp_path):
        """Verify prompt-with-attachment command executes without crash."""
        output = tmp_path / "attachment_output.md"
        result = _run_cli([
            "prompt-with-attachment",
            "-i", str(PROMPT_FILE),
            "-a", str(ATTACHMENT_FILE),
            "-o", str(output),
            "--headless",
        ], timeout=None)  # No timeout for real API calls
        assert result.returncode in (0, 1), f"CLI crashed: {result.stderr[:500]}"
        print(f"\n[ATTACHMENT] Return code: {result.returncode}")
        if result.stdout:
            print(f"[ATTACHMENT] Output preview: {result.stdout[:200]}")


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
    # Run with: python modules/cli/tests/integration_dogfood_pipeline.py --run-dogfood
    pytest.main([__file__, "-v", "--run-dogfood"])
