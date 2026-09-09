"""CLI surface: interactive controller — TUI entry wrapper.

Smart surface: presentation only. Interactive mode is owned by the Textual
TUI app (surface_cli_tui_app.QwenTuiApp); this wrapper injects the specialized
pipeline orchestrators, workspace provisioner, and setup orchestrator, and also
supports headless single-file execution when a config is supplied.
"""

from __future__ import annotations

import sys

from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.utility_core_response import error_response, safe_handle, success_response


class InteractiveController:
    """Interactive TUI controller — delegates to the TUI app and orchestrators."""

    def __init__(
        self,
        workspace: IWorkspaceProtocol,
        direct: IDirectPromptAggregate,
        file_only: IPromptFileAggregate,
        attachment: IAttachmentPromptAggregate,
        setup: ISetupAggregate | None = None,
        session: ISessionAggregate | None = None,
        jobs: IJobManagerAggregate | None = None,
    ) -> None:
        """Inject the specialized pipeline orchestrators, workspace, and setup."""
        self._workspace = workspace
        self._direct = direct
        self._file_only = file_only
        self._attachment = attachment
        self._setup = setup
        self._session = session
        self._jobs = jobs

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
                    "  qwen-web-cli prompt-direct -t \"Summarize this\" [--json]\n"
                    "  qwen-web-cli prompt-only -i prompt.md [--json]\n"
                    "  qwen-web-cli prompt-with-attachment -i prompt.md -a report.pdf [--json]\n"
                    "Then verify your environment with: qwen-web-cli doctor"
                ),
                "validation_error",
                "cli-400",
            )

        if prompt:
            from modules.cli.src.surface_cli_tui_app import QwenTuiApp

            app = QwenTuiApp(
                self._workspace,
                self._direct,
                self._file_only,
                self._attachment,
                self._setup,
                self._session,
                self._jobs,
            )
            app.run()
            return success_response("TUI Session Closed.")

        if cfg is None:
            return success_response("Exited.")

        # C4: single shared dispatcher with the run subcommand.
        from modules.cli.src.surface_cli_run_command import dispatch_run

        envelope = dispatch_run(cfg, self._direct, self._file_only, self._attachment)
        if not envelope.get("success", False):
            return envelope
        return success_response(envelope.get("result"))
