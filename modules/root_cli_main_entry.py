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
  qwen-web-arwaky sessions                          {list|login|health-check|remove|status}
  qwen-web-arwaky jobs                              {submit|status|list|cleanup}
  qwen-web-arwaky swarm                             {start|status|cancel}
  qwen-web-arwaky observability                     {report|status}
  qwen-web-arwaky doctor [--json] [--smoke]
  qwen-web-arwaky update [--check] [--force] [--rollback VERSION]
  qwen-web-arwaky mcp
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

from modules.cli.src.surface_cli_init_command import handle as handle_init_command
from modules.cli.src.surface_cli_interactive_controller import InteractiveController
from modules.cli.src.surface_cli_jobs_command import handle as handle_jobs_command
from modules.cli.src.surface_cli_login_command import handle as handle_login_command
from modules.cli.src.surface_cli_observability_command import handle as handle_observability_command
from modules.cli.src.surface_cli_run_command import handle as handle_run_command
from modules.cli.src.surface_cli_sessions_command import handle_sessions
from modules.cli.src.surface_cli_swarm_command import handle as handle_swarm_command
from modules.cli.src.surface_cli_update_command import handle as handle_update_command
from modules.cli.src.surface_cli_update_command import handle_rollback
from modules.root_core_container import SharedContainer
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_SESSION,
    SESSIONS_DIR,
)
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.taxonomy_session_vo import RotatorRequest
from modules.shared.src.utility_core_env import install_settings
from modules.shared.src.utility_core_prompt_template import (
    is_prompt_role,
    materialize_role_template,
    resolve_prompt_path,
)

_ERROR_PREFIX = "[ERROR]"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments using subcommand-based interface."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "-v", "--verbose", action="store_true", default=argparse.SUPPRESS, help="Enable verbose debug event logging"
    )
    # Issue #283: model selection is stakeholder-configurable. --model takes
    # precedence over QWEN_MODEL, which takes precedence over QWEN_DEFAULT_MODEL.
    parent.add_argument("--model", default=None, help="Qwen model to target (default: $QWEN_MODEL, else Qwen3.8-Max)")

    p = argparse.ArgumentParser(
        prog="qwen-web-arwaky",
        description="Automate chat.qwen.ai without an API key.",
        parents=[parent],
    )
    sub = p.add_subparsers(dest="action", metavar="ACTION")

    # ── doctor ────────────────────────────────────────────────────────────────
    p_doctor = sub.add_parser("doctor", help="Run system environment and health diagnostics", parents=[parent])
    p_doctor.add_argument("--json", action="store_true", help="Format diagnostic output as JSON")
    p_doctor.add_argument(
        "--smoke",
        action="store_true",
        help="Run headless browser smoke test (requires valid saved session)",
    )

    # ── init ──────────────────────────────────────────────────────────────────
    p_init = sub.add_parser("init", help="Initialize workspace (.agents/skills + .qwen-web symlinks)", parents=[parent])
    p_init.add_argument("--dir", dest="target_dir", default=None, help="Target directory (default: cwd)")

    # ── login ─────────────────────────────────────────────────────────────────
    p_login = sub.add_parser(
        "login",
        help="Open browser for manual login and save session",
        parents=[parent],
    )
    p_login.add_argument(
        "--session",
        required=True,
        metavar="NAME",
        help="Session account name (e.g., personal, work). Resolves to SESSIONS_DIR/NAME.",
    )

    # ── update ────────────────────────────────────────────────────────────────
    p_update = sub.add_parser(
        "update",
        help="Self-update qwen-web-arwaky and synchronize Playwright Chromium binaries",
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
    p_update.add_argument("--json", action="store_true", help="Format output as JSON")
    p_update.add_argument(
        "--rollback",
        metavar="VERSION",
        default=None,
        help="Roll back to a previous package version instead of upgrading",
    )

    # ── sessions ────────────────────────────────────────────────────────────
    p_sessions = sub.add_parser("sessions", help="Manage Qwen login sessions", parents=[parent])
    sessions_sub = p_sessions.add_subparsers(dest="session_command")
    sessions_sub.add_parser("list", help="List all sessions")
    sessions_login = sessions_sub.add_parser("login", help="Add a new session")
    sessions_login.add_argument("--name", required=True, help="Session name (e.g., personal, work)")
    sessions_sub.add_parser("health-check", help="Check health of all sessions")
    sessions_remove = sessions_sub.add_parser("remove", help="Remove a session")
    sessions_remove.add_argument("session_id", help="Session ID to remove")
    sessions_sub.add_parser("status", help="Show detailed session status")

    # ── prompt-direct ─────────────────────────────────────────────────────────
    p_direct = sub.add_parser("prompt-direct", help="Send an inline text prompt to Qwen", parents=[parent])
    p_direct.add_argument("-t", "--text", required=True, help="Prompt text to send directly")
    p_direct.add_argument("-o", "--output-path", default=None, help="Output file path")
    p_direct.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,  # U3: accepts --headless / --no-headless
        default=True,  # matches TUI Switch and MCP default
        help="Run browser headlessly (default: true; use --no-headless to watch)",
    )
    p_direct.add_argument("--json", action="store_true", help="Format output as JSON")

    # ── prompt-only ───────────────────────────────────────────────────────────
    p_only = sub.add_parser("prompt-only", help="Process a prompt file (no attachment)", parents=[parent])
    p_only.add_argument(
        "-i",
        "-p",
        "--prompt-path",
        required=True,
        help="Path to prompt file OR built-in role template (any .md file in modules/templates/)",
    )
    p_only.add_argument("-o", "--output-path", default=None, help="Output file path")
    p_only.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser headlessly (default: true; use --no-headless to watch)",
    )
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
        help="Path to prompt file OR built-in role template (any .md file in modules/templates/)",
    )
    p_attach.add_argument("-a", "--attachment-path", required=True, help="Path to file to attach")
    p_attach.add_argument("-o", "--output-path", default=None, help="Output file path")
    p_attach.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser headlessly (default: true; use --no-headless to watch)",
    )
    p_attach.add_argument("--json", action="store_true", help="Format output as JSON")

    # ── mcp ───────────────────────────────────────────────────────────────────
    sub.add_parser("mcp", help="Run as Model Context Protocol (MCP) server over stdio", parents=[parent])

    # ── jobs ──────────────────────────────────────────────────────────────────
    p_jobs = sub.add_parser(
        "jobs",
        help="Manage asynchronous background prompt jobs (submit, status, list, cleanup)",
        parents=[parent],
    )
    jobs_sub = p_jobs.add_subparsers(dest="job_command")
    jobs_submit = jobs_sub.add_parser("submit", help="Submit a prompt job to the background worker pool")
    jobs_submit.add_argument(
        "-i",
        "-p",
        "--prompt-path",
        required=True,
        help="Path to prompt file OR built-in role template (any .md file in modules/templates/)",
    )
    jobs_submit.add_argument("-a", "--attachment-path", default=None, help="Optional file to attach")
    jobs_submit.add_argument("-o", "--output-path", default=None, help="Output file path")
    jobs_submit.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser headlessly (default: true; use --no-headless to watch)",
    )
    jobs_submit.add_argument("--json", action="store_true", help="Format output as JSON")
    jobs_status = jobs_sub.add_parser("status", help="Check status of a background job")
    jobs_status.add_argument("job_id", help="Job ID to query")
    jobs_status.add_argument("--json", action="store_true", help="Format output as JSON")
    jobs_list = jobs_sub.add_parser("list", help="List recent background jobs")
    jobs_list.add_argument("--limit", type=int, default=10, help="Maximum jobs to list (default: 10)")
    jobs_list.add_argument("--json", action="store_true", help="Format output as JSON")
    jobs_cleanup = jobs_sub.add_parser("cleanup", help="Remove stale job records past their retention window")
    jobs_cleanup.add_argument("--json", action="store_true", help="Format output as JSON")

    # ── swarm ────────────────────────────────────────────────────────────────
    p_swarm = sub.add_parser(
        "swarm",
        help="Run a multi-agent Swarm fan-out across role templates",
        parents=[parent],
    )
    swarm_sub = p_swarm.add_subparsers(dest="swarm_command")
    swarm_start = swarm_sub.add_parser("start", help="Start a Swarm fan-out over a file or folder")
    swarm_start.add_argument("input", help="Path to file or folder to fan out across all role templates")
    swarm_start.add_argument("--json", action="store_true", help="Format output as JSON")
    swarm_status = swarm_sub.add_parser("status", help="Show status of a running or completed Swarm")
    swarm_status.add_argument("swarm_id", help="Swarm ID to query")
    swarm_status.add_argument("--json", action="store_true", help="Format output as JSON")
    swarm_cancel = swarm_sub.add_parser("cancel", help="Cancel a running Swarm")
    swarm_cancel.add_argument("swarm_id", help="Swarm ID to cancel")
    swarm_cancel.add_argument("--json", action="store_true", help="Format output as JSON")

    # ── observability ────────────────────────────────────────────────────────
    p_obs = sub.add_parser(
        "observability",
        help="Query observability status: run metrics and quality reports",
        parents=[parent],
    )
    obs_sub = p_obs.add_subparsers(dest="observability_command")
    obs_report = obs_sub.add_parser("report", help="Write and display the quality report for the last run")
    obs_report.add_argument("--json", action="store_true", help="Format output as JSON")
    obs_status = obs_sub.add_parser("status", help="Show current status file contents")
    obs_status.add_argument("--json", action="store_true", help="Format output as JSON")

    return p.parse_args(argv)


def _resolve_session_for_prompt(args: argparse.Namespace, container: SharedContainer) -> None:
    """Resolve session path for prompt commands using rotation.

    Only runs for prompt-direct / prompt-only / prompt-with-attachment when
    multiple sessions exist. Picks a healthy session and overrides cfg.session_path.
    """
    action = getattr(args, "action", None)
    if action not in ("prompt-direct", "prompt-only", "prompt-with-attachment"):
        return

    pool = container.session_manager.load_pool()
    if pool.total_count <= 1:
        return

    async def _pick() -> Path | None:
        response = await container.session_rotator.rotate(RotatorRequest())
        return response.session.path if response.session else None

    try:
        session_path = asyncio.run(_pick())
    except Exception:
        session_path = None

    if session_path is not None and session_path != DEFAULT_SESSION:
        args._session_override = session_path


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

    # Reject an empty direct prompt here rather than deep in dispatch: building
    # the config and initialising observability first wastes the whole setup
    # path before surfacing a generic message.
    if action == "prompt-direct" and not (text or "").strip():
        raise ValueError(
            "Empty prompt text for prompt-direct.\n"
            "Why: --text/-t must carry non-empty content to send to Qwen.\n"
            "How to fix: supply a prompt, e.g.\n"
            '  qwen-web-arwaky prompt-direct -t "Summarize this document"'
        )

    raw_prompt = getattr(args, "prompt_path", None)
    raw_attach = getattr(args, "attachment_path", None)
    raw_output = getattr(args, "output_path", None)

    prompt_label: str = ""

    if raw_prompt:
        if is_prompt_role(raw_prompt):
            prompt_p = materialize_role_template(raw_prompt)
            prompt_label = raw_prompt.strip().lower()
        else:
            prompt_p = resolve_prompt_path(raw_prompt)
            if not prompt_p.exists():
                raise ValueError(f"Prompt file not found: {prompt_p}")

    if raw_attach:
        file_p = Path(raw_attach).resolve()
        if not file_p.exists():
            raise ValueError(f"Attachment file not found: {file_p}")

    if raw_output:
        out_p = Path(raw_output)
    else:
        # Prefer the project-local .qwen-web/output when it is a symlink to the
        # XDG DEFAULT_OUTPUT (i.e. `qwa init` was run). Otherwise fall back to
        # the XDG DEFAULT_OUTPUT directly so output always lands in the
        # standardized location even if the local dir is missing or stale.
        local_out = Path.cwd() / ".qwen-web" / "output"
        if local_out.is_dir() and not local_out.is_symlink():
            # A real directory means `qwa init` was not run; use XDG.
            base_dir = DEFAULT_OUTPUT
        else:
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
        "jobs": "direct",
        "swarm": "single",
        "observability": "direct",
    }

    # Check for session path override from rotation
    session_name = getattr(args, "session", None)
    if action == "login" and session_name:
        # login: resolve --session NAME to SESSIONS_DIR/NAME
        effective_session = SESSIONS_DIR / session_name
    else:
        effective_session = Path(getattr(args, "_session_override", DEFAULT_SESSION))
    model = str(getattr(args, "model", None) or "").strip()

    return AppConfig(
        mode=mode_map.get(action, "direct"),
        input_path=prompt_p or dummy_path,
        output_path=out_p,
        session_path=effective_session,
        log_path=DEFAULT_LOG,
        headless=headless,
        verbose=verbose,
        prompt_file=prompt_p,
        prompt_path=prompt_p,
        file_path=file_p,
        inline_prompt=action == "prompt-direct",
        inline_prompt_text=text if action == "prompt-direct" else None,
        model=model,
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
                "  qwen-web-arwaky doctor\n"
                '  qwen-web-arwaky prompt-direct -t "Your prompt"\n'
                "  qwen-web-arwaky prompt-only -i input/prompt.md\n\n"
                "Run `qwen-web-arwaky --help` to see all available commands.",
                file=sys.stderr,
            )
            return 1

        # Ensure observability (structlog + app.jsonl file handler) is wired up
        # even in interactive TUI mode, so logs are persisted to DEFAULT_LOG
        # instead of being dropped. (FileHandler is otherwise only attached in
        # the non-interactive CLI subcommand path below.)
        # attach_stderr=False: the TUI owns the terminal canvas. Playwright
        # browser callbacks emit log records from their own threads; a stderr
        # handler would write them straight to the terminal, corrupting the UI.
        container.observability.setup_observability(log_path=DEFAULT_LOG, attach_stderr=False)

        result = InteractiveController(
            container.workspace,
            container.agent_direct_prompt_orchestrator,
            container.agent_prompt_file_orchestrator,
            container.agent_attachment_prompt_orchestrator,
            container.slot_plan,
            container.agent_setup_orchestrator,
            container.agent_session_orchestrator,
            container.agent_job_orchestrator,
            container.agent_swarm_orchestrator,
            container.session_manager,
            container.updater,
            container.job_storage,
        ).run()
        return _result_exit_code(result, json_output=json_output)

    action = getattr(args, "action", None)

    if action == "doctor":
        from modules.cli.src.surface_cli_doctor_command import run_doctor

        return run_doctor(
            json_output=bool(getattr(args, "json", False)),
            smoke=bool(getattr(args, "smoke", False)),
            session=container.agent_session_orchestrator,
            session_manager=container.session_manager,
        )

    if action == "login":
        if cfg is None:
            print(f"{_ERROR_PREFIX} Missing login configuration.", file=sys.stderr)
            return 1
        return _run_manual_login(cfg, container, json_output=json_output)

    if action == "init":
        result = handle_init_command(args, container.workspace)
        return _result_exit_code(result, json_output=json_output)

    if action == "update":
        if getattr(args, "rollback", None):
            return handle_rollback(args, container.agent_update_orchestrator)
        result = handle_update_command(args, container.updater)
        return _result_exit_code(result, json_output=json_output)

    if action == "jobs":
        return handle_jobs_command(args, container.agent_job_orchestrator, container.job_storage)

    if action == "swarm":
        return handle_swarm_command(args, container.agent_swarm_orchestrator)

    if action == "observability":
        return handle_observability_command(args, container.agent_logging_orchestrator, container.metrics)

    if action == "sessions":
        return handle_sessions(args)

    if cfg is None:
        print(f"{_ERROR_PREFIX} Missing CLI configuration.", file=sys.stderr)
        return 1

    resolved_log_path = cfg.log_path if cfg.log_path is not None else DEFAULT_LOG
    container.observability.setup_observability(log_path=resolved_log_path, verbose=cfg.verbose)

    args._cfg = cfg
    # Resolve session rotation before dispatch
    _resolve_session_for_prompt(args, container)
    result = handle_run_command(
        args,
        cfg,
        container.agent_direct_prompt_orchestrator,
        container.agent_prompt_file_orchestrator,
        container.agent_attachment_prompt_orchestrator,
    )
    container.observability.metrics.record_execution(bool(result.get("success")))
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

    # The TUI Settings screen persists operator overrides to an XDG file. They
    # must be in the environment before the container is built, because the
    # capabilities that read them (capacity, sandbox, model) are constructed
    # once and never re-read the registry.
    install_settings()

    cfg: AppConfig | None = None
    if args is not None:
        action = getattr(args, "action", None)
        # actions that do not need an AppConfig (no prompt path, no browser run)
        no_cfg_actions = ("init", "jobs", "swarm", "observability", "sessions")
        if action not in no_cfg_actions:
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
    result = handle_login_command(
        None,
        container.agent_session_orchestrator,
        container.agent_setup_orchestrator,
        cfg,
    )
    return _result_exit_code(result, json_output=json_output)


if __name__ == "__main__":
    sys.exit(main())
