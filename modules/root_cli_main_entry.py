"""qwen-web-arwaky v5: Production-grade automation for chat.qwen.ai.

Root layer: CLI entry point — subcommand-based argument parsing, validation,
lifecycle guards, and dispatch to the CLI surface commands via DI container.

Usage:
  qwen-web-arwaky init                              [--dir TARGET_DIR]
  qwen-web-arwaky login
  qwen-web-arwaky prompt-direct  --text "..."       [--output-path FILE] [--headless] [--json]
  qwen-web-arwaky prompt-only    --prompt-path FILE [--output-path FILE] [--headless]
  qwen-web-arwaky prompt-with-attachment \\
                                 --prompt-path FILE --attachment-path FILE \\
                                 [--output-path FILE] [--headless]
  qwen-web-arwaky mcp
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import modules.cli.src.surface_cli_init_command as surface_cli_init_command
import modules.cli.src.surface_cli_interactive_controller as surface_cli_interactive_controller
import modules.cli.src.surface_cli_login_command as surface_cli_login_command
import modules.cli.src.surface_cli_run_command as surface_cli_run_command
import modules.cli.src.surface_cli_update_command as surface_cli_update_command
from modules.core.src.root_core_container import SharedContainer
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG, DEFAULT_OUTPUT, DEFAULT_SESSION
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.utility_core_prompt_template import is_prompt_role, materialize_role_template

_ERROR_PREFIX = "[ERROR]"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments using subcommand-based interface."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "-v", "--verbose", action="store_true", default=argparse.SUPPRESS, help="Enable verbose debug event logging"
    )

    p = argparse.ArgumentParser(
        prog="qwen-web-arwaky",
        description="Automate chat.qwen.ai without an API key.",
        parents=[parent],
    )
    sub = p.add_subparsers(dest="action", metavar="ACTION")

    # ── doctor ────────────────────────────────────────────────────────────────
    p_doctor = sub.add_parser("doctor", help="Run system environment and health diagnostics", parents=[parent])
    p_doctor.add_argument("--json", action="store_true", help="Format diagnostic output as JSON")

    # ── init ──────────────────────────────────────────────────────────────────
    p_init = sub.add_parser("init", help="Initialize workspace (.agents/skills + .qwen-web symlinks)", parents=[parent])
    p_init.add_argument("--dir", dest="target_dir", default=None, help="Target directory (default: cwd)")

    # ── login ─────────────────────────────────────────────────────────────────
    sub.add_parser("login", help="Open browser for manual login and save session", parents=[parent])

    # ── update ────────────────────────────────────────────────────────────────
    p_update = sub.add_parser(
        "update",
        help="Self-update qwen-web-cli and synchronize Playwright Chromium binaries",
        parents=[parent],
    )
    p_update.add_argument(
        "--check",
        action="store_true",
        help="Only compare current vs latest version; make no system changes",
    )
    p_update.add_argument(
        "--force",
        action="store_true",
        help="Reinstall package and browser binaries even when already up to date",
    )

    # ── prompt-direct ─────────────────────────────────────────────────────────
    p_direct = sub.add_parser("prompt-direct", help="Send an inline text prompt to Qwen", parents=[parent])
    p_direct.add_argument("-t", "--text", required=True, help="Prompt text to send directly")
    p_direct.add_argument("-o", "--output-path", default=None, help="Output file path")
    p_direct.add_argument("--headless", action="store_true", help="Run browser headlessly")
    p_direct.add_argument("--json", action="store_true", help="Format output as JSON")

    # ── prompt-only ───────────────────────────────────────────────────────────
    p_only = sub.add_parser("prompt-only", help="Process a prompt file (no attachment)", parents=[parent])
    p_only.add_argument(
        "-i",
        "-p",
        "--prompt-path",
        required=True,
        help="Path to prompt file OR built-in role template (architect|backend|frontend|analyst)",
    )
    p_only.add_argument("-o", "--output-path", default=None, help="Output file path")
    p_only.add_argument("--headless", action="store_true", help="Run browser headlessly")
    p_only.add_argument("--json", action="store_true", help="Format output as JSON")

    # ── prompt-with-attachment ────────────────────────────────────────────────
    p_attach = sub.add_parser(
        "prompt-with-attachment", help="Process a prompt file with a file attachment", parents=[parent]
    )
    p_attach.add_argument(
        "-i",
        "-p",
        "--prompt-path",
        required=True,
        help="Path to prompt file OR built-in role template (architect|backend|frontend|analyst)",
    )
    p_attach.add_argument("-a", "--attachment-path", required=True, help="Path to file to attach")
    p_attach.add_argument("-o", "--output-path", default=None, help="Output file path")
    p_attach.add_argument("--headless", action="store_true", help="Run browser headlessly")
    p_attach.add_argument("--json", action="store_true", help="Format output as JSON")

    # ── mcp ───────────────────────────────────────────────────────────────────
    sub.add_parser("mcp", help="Run as Model Context Protocol (MCP) server over stdio", parents=[parent])

    return p.parse_args(argv)


def _build_config(args: argparse.Namespace) -> AppConfig:
    """Build AppConfig from parsed subcommand args using hardcoded defaults."""
    action = args.action
    headless = bool(getattr(args, "headless", False))
    verbose = bool(getattr(args, "verbose", False))
    dummy_path = Path(os.devnull)

    prompt_p: Path | None = None
    file_p: Path | None = None
    out_p: Path | None = None
    text: str | None = getattr(args, "text", None)

    raw_prompt = getattr(args, "prompt_path", None)
    raw_attach = getattr(args, "attachment_path", None)
    raw_output = getattr(args, "output_path", None)

    prompt_label: str = ""

    if raw_prompt:
        if is_prompt_role(raw_prompt):
            prompt_p = materialize_role_template(raw_prompt)
            prompt_label = raw_prompt.strip().lower()
        else:
            prompt_p = Path(raw_prompt).resolve()
            if not prompt_p.exists():
                raise ValueError(f"Prompt file not found: {prompt_p}")

    if raw_attach:
        file_p = Path(raw_attach).resolve()
        if not file_p.exists():
            raise ValueError(f"Attachment file not found: {file_p}")

    if raw_output:
        out_p = Path(raw_output)
    else:
        local_out = Path.cwd() / ".qwen-web" / "output"
        base_dir = local_out if local_out.exists() else DEFAULT_OUTPUT
        if prompt_p:
            out_name = prompt_label or prompt_p.stem
            out_p = base_dir / f"{out_name}_output.md"
        elif text:
            out_p = base_dir / "direct_output.md"
        else:
            out_p = base_dir

    mode_map = {
        "login": "login",
        "prompt-direct": "direct",
        "prompt-only": "single",
        "prompt-with-attachment": "single",
        "init": "init",
        "mcp": "mcp",
    }

    return AppConfig(
        mode=mode_map.get(action, "direct"),
        input_path=prompt_p or dummy_path,
        output_path=out_p,
        done_path=dummy_path,
        failed_path=dummy_path,
        proc_path=dummy_path,
        session_path=DEFAULT_SESSION,
        log_path=DEFAULT_LOG,
        headless=headless,
        verbose=verbose,
        prompt_file=prompt_p,
        prompt_path=prompt_p,
        file_path=file_p,
        inline_prompt=action == "prompt-direct",
        inline_prompt_text=text if action == "prompt-direct" else None,
    )


@lru_cache(maxsize=1)
def _default_container() -> SharedContainer:
    """Build the default auto-wired DI container (cached singleton)."""
    return SharedContainer()


def _result_exit_code(result: dict[str, object], json_output: bool = False) -> int:
    """Convert a surface response envelope to a CLI exit code."""
    if result.get("success"):
        if json_output:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(result.get("message", ""))
        return 0
    if json_output:
        print(json.dumps(result, indent=2, default=str))
    print(f"{_ERROR_PREFIX} {result.get('error') or 'Unknown error'}", file=sys.stderr)
    return _exit_code_for_result(result)


def _exit_code_for_result(result: dict[str, object]) -> int:
    """Map a failed response envelope to a process exit code."""
    error = str(result.get("error") or "")
    if "AUTH_REQUIRED" in error or "not authenticated" in error.lower() or "session expired" in error.lower():
        return 2
    return 1


def _dispatch(
    container: SharedContainer,
    _raw_argv: list[str],
    args: argparse.Namespace | None,
    cfg: AppConfig | None,
) -> int:
    """Dispatch one already-parsed CLI invocation inside the Linux lifecycle."""
    json_output = bool(getattr(args, "json", False)) if args is not None else False
    if args is None:
        if not sys.stdin.isatty():
            print(
                f"{_ERROR_PREFIX} Interactive TUI mode requires a terminal (TTY).\n\n"
                "If you are running in a non-interactive environment, use a subcommand instead:\n"
                "  qwen-web-cli doctor\n"
                '  qwen-web-cli prompt-direct -t "Your prompt"\n'
                "  qwen-web-cli prompt-only -i input/prompt.md\n\n"
                "Run `qwen-web-cli --help` to see all available commands.",
                file=sys.stderr,
            )
            return 1

        result = surface_cli_interactive_controller.InteractiveController(
            container.workspace,
            container.agent_direct_prompt_orchestrator,
            container.agent_prompt_file_orchestrator,
            container.agent_attachment_prompt_orchestrator,
            container.agent_setup_orchestrator,
            container.agent_session_orchestrator,
            container.agent_job_orchestrator,
        ).run()
        return _result_exit_code(result, json_output=json_output)

    action = getattr(args, "action", None)

    if action == "doctor":
        from modules.cli.src.surface_cli_doctor_command import run_doctor

        return run_doctor(json_output=bool(getattr(args, "json", False)))

    if action == "login":
        if cfg is None:
            print(f"{_ERROR_PREFIX} Missing login configuration.", file=sys.stderr)
            return 1
        return _run_manual_login(cfg, container, json_output=json_output)

    if action == "init":
        result = surface_cli_init_command.handle(args, container.workspace)
        return _result_exit_code(result, json_output=json_output)

    if action == "update":
        result = surface_cli_update_command.handle(args, container.updater)
        return _result_exit_code(result, json_output=json_output)

    if cfg is None:
        print(f"{_ERROR_PREFIX} Missing CLI configuration.", file=sys.stderr)
        return 1

    container.observability.setup_observability(log_path=cfg.log_path, verbose=cfg.verbose)

    args._cfg = cfg
    result = surface_cli_run_command.handle(
        args,
        cfg,
        container.agent_direct_prompt_orchestrator,
        container.agent_prompt_file_orchestrator,
        container.agent_attachment_prompt_orchestrator,
    )
    return _result_exit_code(result, json_output=json_output)


def main(argv: list[str] | None = None) -> int:
    """Run the main entrypoint for qwen-web-arwaky."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(raw_argv) if raw_argv else None

    # MCP is a separate runtime — never enters the CLI lifecycle path.
    if args and getattr(args, "action", None) == "mcp":
        from modules.root_mcp_main_entry import run_mcp_server

        run_mcp_server()
        return 0

    cfg: AppConfig | None = None
    if args is not None:
        action = getattr(args, "action", None)
        if action not in ("init",):
            try:
                cfg = _build_config(args)
            except (OSError, ValueError) as exc:
                print(f"{_ERROR_PREFIX} {exc}", file=sys.stderr)
                return 1

    try:
        return _dispatch(_default_container(), raw_argv, args, cfg)
    except Exception as exc:
        from modules.shared.src.utility_core_exit import exit_code_for

        print(f"{_ERROR_PREFIX} {exc}", file=sys.stderr)
        return exit_code_for(exc)


def _run_manual_login(cfg: AppConfig, container: SharedContainer | None = None, json_output: bool = False) -> int:
    """Launch visible browser for interactive login."""
    if container is None:
        container = _default_container()
    result = surface_cli_login_command.handle(
        None,
        container.agent_session_orchestrator,
        container.agent_setup_orchestrator,
        cfg,
    )
    return _result_exit_code(result, json_output=json_output)


if __name__ == "__main__":
    sys.exit(main())
