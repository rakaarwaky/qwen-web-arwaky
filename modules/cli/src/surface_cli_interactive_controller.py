"""CLI surface: interactive controller — TUI entry wrapper.

Smart surface: presentation only. Interactive mode is owned by the Textual
TUI app (modules.tui surface_tui_app_screen.QwenTuiApp); this wrapper injects the specialized
pipeline orchestrators, workspace provisioner, and setup orchestrator, and also
supports headless single-file execution when a config is supplied.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.common.utility_response_normalizer import error_response, safe_handle, success_response
from modules.shared.src.config.contract_config_aggregate import IConfigAggregate
from modules.shared.src.jobs.contract_jobs_aggregate import IJobManagerAggregate
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.taxonomy_session_vo import SessionList, SessionRequest, SessionResponse
from modules.shared.src.swarm.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.update.contract_update_aggregate import IUpdateAggregate


def _pool_aggregate(session_manager: Any) -> ISessionAggregate | None:
    """Adapt ``session_manager.load_pool()`` to the session aggregate contract.

    The doctor reads the pool through ``ISessionAggregate.execute``; when no
    orchestrator is wired the pool itself still answers the read verbs from
    ``session_manager``, so the doctor's source of truth stays the disk pool
    rather than a fabricated empty answer (issue 5). A host with no
    ``session_manager`` wired keeps no pool source at all, so the caller
    reports the wiring gap instead of pretending a pool exists.
    """

    class _PoolAggregate(ISessionAggregate):
        """Pool-only aggregate: the read verbs answer from the live pool."""

        def __init__(self, manager: Any) -> None:
            self._manager = manager

        def execute(self, request: SessionRequest) -> SessionResponse:
            if request.verb == "list_sessions":
                pool = self._manager.load_pool()
                return SessionResponse(
                    sessions=SessionList(list(pool.sessions)),
                    message=f"{len(pool.sessions)} session(s)",
                )
            return SessionResponse(valid=False, message=f"No session orchestrator wired for {request.verb}.")

    if session_manager is None:
        return None
    return _PoolAggregate(session_manager)


class InteractiveController:
    """Interactive TUI controller — delegates to the TUI app and orchestrators."""

    def __init__(
        self,
        workspace: IConfigAggregate,
        prompt: IPromptAggregate,
        slot_config: IConfigAggregate,
        session: ISessionAggregate | None = None,
        jobs: IJobManagerAggregate | None = None,
        swarm: ISwarmAggregate | None = None,
        updater: IUpdateAggregate | None = None,
        session_manager: Any | None = None,
        job_storage: Any | None = None,
        session_rotator: Any | None = None,
        doctor_runner: Any | None = None,
    ) -> None:
        """Inject the specialized pipeline orchestrators, workspace, and setup."""
        self._workspace = workspace
        self._prompt = prompt
        self._slot_config = slot_config
        self._session = session
        self._jobs = jobs
        self._swarm = swarm
        self._updater = updater
        self._session_manager = session_manager
        self._job_storage = job_storage
        self._session_rotator = session_rotator
        self._doctor_runner = doctor_runner

    @safe_handle
    def run(self, cfg: AppConfig | None = None, *, prompt: bool = True) -> dict[str, object]:
        """Present the Textual Obsidian Nebula TUI and execute interactions."""
        if prompt and not sys.stdin.isatty():
            # A1: actionable, example-driven non-TTY rejection (FR-002.5 + NFR).
            return error_response(
                RuntimeError(
                    "Interactive mode requires a TTY, but stdin is not interactive (pipe/cron detected).\n"
                    "Why: the Obsidian Nebula TUI needs a real terminal to render.\n"
                    "How to fix: use a non-interactive subcommand instead, e.g.:\n"
                    '  qwen-web-arwaky prompt direct -t "Summarize this" [--json]\n'
                    "  qwen-web-arwaky prompt file -i prompt.md [--json]\n"
                    "  qwen-web-arwaky prompt attach -i prompt.md -a report.pdf [--json]\n"
                    "Then verify your environment with: qwen-web-arwaky doctor"
                ),
                "validation_error",
                "cli-400",
            )

        if prompt:
            from modules.tui.src.surface_tui_app_screen import QwenTuiApp

            doctor_runner = self._doctor_runner
            if doctor_runner is None:
                from modules.cli.src.surface_cli_doctor_command import run_doctor_checks

                # The pool is the doctor's single source of truth, so the
                # runner always carries a session aggregate: the wired one
                # when the container built it, otherwise the pool itself read
                # through ``session_manager.load_pool()`` — never a stub that
                # answers an empty pool without consulting disk (issue 5).
                aggregate = self._session if self._session is not None else _pool_aggregate(self._session_manager)
                if aggregate is None:
                    raise ValueError(
                        "InteractiveController requires a session aggregate (ISessionAggregate) or a "
                        "session_manager to read the session pool for the doctor pane; "
                        "pass session=, session_manager=, or doctor_runner=."
                    )

                def doctor_runner() -> list[dict[str, Any]]:
                    return run_doctor_checks(session=aggregate)

            app = QwenTuiApp(
                self._workspace,
                self._prompt,
                self._slot_config,
                self._session,
                self._jobs,
                self._swarm,
                self._updater,
                self._session_manager,
                self._job_storage,
                self._session_rotator,
                doctor_runner=doctor_runner,
            )
            app.run()
            return success_response("TUI Session Closed.")

        if cfg is None:
            return success_response("Exited.")

        from modules.cli.src.surface_cli_run_command import dispatch_run

        def _pick() -> Path | None:
            """Resolve a pool session for the headless run.

            The headless path builds its own AppConfig, so without a
            resolver the pool selection would be dropped and an empty
            default session used instead of a logged-in profile.
            """
            if self._session_rotator is None:
                return None
            try:
                from modules.shared.src.session.taxonomy_session_vo import RotatorRequest

                response = asyncio.run(self._session_rotator.rotate(RotatorRequest()))
                return response.session.path if response.session else None
            except Exception as exc:
                # Degradation is non-fatal: warn on stderr and keep the default session.
                print(f"[WARN] Session rotation failed; falling back to the default session: {exc}", file=sys.stderr)
                return None

        return dispatch_run(cfg, self._prompt, session_resolver=_pick)
