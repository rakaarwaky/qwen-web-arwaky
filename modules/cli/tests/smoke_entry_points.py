"""Tests for the application entry points — `root_cli_main_entry` and `root_mcp_main_entry`."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


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


def test_cli_barrel_re_exports_every_surface() -> None:
    """The CLI barrel must name all ten surface modules in ``__all__``.

    A surface added without the barrel row silently breaks the
    single-import entry-point contract, so the module count and every
    name are pinned here.
    """
    import modules.cli.src as cli_barrel

    expected = [
        "surface_cli_doctor_command",
        "surface_cli_init_command",
        "surface_cli_interactive_controller",
        "surface_cli_jobs_command",
        "surface_cli_observability_command",
        "surface_cli_json_hook",
        "surface_cli_run_command",
        "surface_cli_sessions_command",
        "surface_cli_swarm_command",
        "surface_cli_update_command",
    ]
    assert cli_barrel.__all__ == expected
    for name in expected:
        assert hasattr(cli_barrel, name), f"barrel missing {name}"


def test_cli_parse_args_verbose_flag() -> None:
    """The CLI entry point must parse -v and --verbose flags correctly."""
    from modules.root_cli_main_entry import _build_config, _parse_args

    args_quiet = _parse_args(["prompt", "direct", "-t", "hello"])
    assert getattr(args_quiet, "verbose", False) is False
    cfg_quiet = _build_config(args_quiet)
    assert cfg_quiet.verbose is False

    args_v_short = _parse_args(["-v", "prompt", "direct", "-t", "hello"])
    assert args_v_short.verbose is True
    cfg_v_short = _build_config(args_v_short)
    assert cfg_v_short.verbose is True

    args_v_long = _parse_args(["prompt", "direct", "-t", "hello", "--verbose"])
    assert args_v_long.verbose is True
    cfg_v_long = _build_config(args_v_long)
    assert cfg_v_long.verbose is True


def test_cli_command_tree_is_grouped() -> None:
    """Every command follows `app <command> [subcommand] [flags/options]`."""
    from modules.root_cli_main_entry import _parse_args

    direct = _parse_args(["prompt", "direct", "-t", "hello"])
    assert direct.action == "prompt"
    assert direct.prompt_command == "direct"

    file_args = _parse_args(["prompt", "file", "-i", "prompt.md"])
    assert file_args.action == "prompt"
    assert file_args.prompt_command == "file"

    attach = _parse_args(["prompt", "attach", "-i", "prompt.md", "-a", "att.pdf"])
    assert attach.action == "prompt"
    assert attach.prompt_command == "attach"

    assert _parse_args(["session", "list"]).session_command == "list"
    assert _parse_args(["session", "health"]).session_command == "health"
    assert _parse_args(["job", "list"]).job_command == "list"
    assert _parse_args(["swarm", "start", "src"]).swarm_command == "start"
    assert _parse_args(["observability", "status"]).observability_command == "status"


def test_cli_prompt_subcommands_select_the_runtime_mode(tmp_path: Path) -> None:
    """`prompt direct` maps to direct mode; file/attach map to single mode."""
    from modules.root_cli_main_entry import _build_config, _parse_args

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("prompt", encoding="utf-8")
    attachment = tmp_path / "att.pdf"
    attachment.write_text("attachment", encoding="utf-8")

    assert _build_config(_parse_args(["prompt", "direct", "-t", "hello"])).mode == "direct"
    assert _build_config(_parse_args(["prompt", "file", "-i", str(prompt_file)])).mode == "single"
    assert (
        _build_config(_parse_args(["prompt", "attach", "-i", str(prompt_file), "-a", str(attachment)])).mode == "single"
    )


def test_legacy_flat_commands_are_rejected() -> None:
    """The pre-standardization flat command names no longer parse."""
    from modules.root_cli_main_entry import _parse_args

    for legacy in (
        "prompt-direct",
        "prompt-only",
        "prompt-with-attachment",
        "login",
        "sessions",
        "jobs",
    ):
        with pytest.raises(SystemExit):
            _parse_args([legacy])
