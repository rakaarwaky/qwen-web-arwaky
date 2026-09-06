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
from modules.shared.src.taxonomy_core_vo import AppConfig, HeadlessFlag
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
            return error_response(
                RuntimeError("Interactive mode requires a TTY. Please provide CLI arguments."),
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

        mode = cfg.mode
        if mode == "direct":
            prompt_text = cfg.inline_prompt_text
            if not prompt_text:
                return error_response(
                    RuntimeError("Missing inline prompt text for direct mode."), "validation_error", "cli-400"
                )
            result = self._direct.process_direct_prompt(
                prompt=prompt_text,
                output_file=cfg.output_path,
                headless=HeadlessFlag(cfg.headless),
            )
        elif mode == "single":
            prompt_file = cfg.prompt_path or cfg.input_path
            if cfg.file_path:
                result = self._attachment.process_prompt_with_attachment(
                    prompt_file=prompt_file,
                    attachment_file=cfg.file_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                )
            else:
                result = self._file_only.process_prompt_file_only(
                    prompt_file=prompt_file,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                )
        else:
            return error_response(RuntimeError(f"Unsupported CLI mode: {mode}"), "validation_error", "cli-400")

        res_str = str(result)
        if res_str.startswith("Execution failed") or res_str.startswith("Error:"):
            return error_response(RuntimeError(res_str), "execution_error", "cli-500")
        return success_response(result)
