"""Tests for the application entry points — `root_cli_main_entry` and `root_mcp_main_entry`."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_entry_runs_help() -> None:
    """Running the CLI entry point with --help must print usage and exit 0."""
    root = Path(__file__).resolve().parent.parent.parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    result = subprocess.run(
        [sys.executable, "-m", "modules.root_cli_main_entry", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0
    assert "usage: qwen-web-arwaky" in result.stdout


def test_cli_entry_is_importable() -> None:
    """The CLI entry point must expose a callable `main`."""
    from modules.root_cli_main_entry import main

    assert callable(main)


def test_mcp_entry_is_importable() -> None:
    """The MCP entry point must expose `run_mcp_server` and `main`."""
    from modules.root_mcp_main_entry import main, run_mcp_server

    assert callable(run_mcp_server)
    assert callable(main)


def test_cli_parse_args_verbose_flag() -> None:
    """The CLI entry point must parse -v and --verbose flags correctly."""
    from modules.root_cli_main_entry import _build_config, _parse_args

    args_quiet = _parse_args(["prompt-direct", "-t", "hello"])
    assert getattr(args_quiet, "verbose", False) is False
    cfg_quiet = _build_config(args_quiet)
    assert cfg_quiet.verbose is False

    args_v_short = _parse_args(["-v", "prompt-direct", "-t", "hello"])
    assert args_v_short.verbose is True
    cfg_v_short = _build_config(args_v_short)
    assert cfg_v_short.verbose is True

    args_v_long = _parse_args(["prompt-direct", "-t", "hello", "--verbose"])
    assert args_v_long.verbose is True
    cfg_v_long = _build_config(args_v_long)
    assert cfg_v_long.verbose is True
