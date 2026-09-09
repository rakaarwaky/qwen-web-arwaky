"""CLI surface: run command — single prompt processing dispatch.

Smart surface: maps parsed args/config to the correct specialized pipeline
orchestrator based on AppConfig.mode, then delegates with zero business logic.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IPromptFileAggregate,
)
from modules.shared.src.taxonomy_core_vo import AppConfig, HeadlessFlag
from modules.shared.src.utility_core_response import (
    detect_processing_failure,
    error_response,
    safe_handle,
    success_response,
)


def _processing_failure_message(result: object) -> str | None:
    """Return a failure reason when a normal core response reports failed work."""
    return detect_processing_failure(result)


def dispatch_run(
    cfg: AppConfig,
    direct: IDirectPromptAggregate,
    file_only: IPromptFileAggregate,
    attachment: IAttachmentPromptAggregate,
) -> dict[str, object]:
    """C4: single shared dispatcher for direct/single modes.

    Used by both ``handle`` (run subcommand) and ``InteractiveController.run``
    so the dispatch semantics stay in exactly one place.
    """
    mode = cfg.mode

    if mode == "direct":
        prompt_text = cfg.inline_prompt_text
        if not prompt_text:
            return error_response(
                RuntimeError("Missing inline prompt text for direct mode."), "validation_error", "cli-400"
            )
        result = direct.process_direct_prompt(
            prompt=prompt_text,
            output_file=cfg.output_path,
            headless=HeadlessFlag(cfg.headless),
        )
    elif mode == "single":
        prompt_file = cfg.prompt_path or cfg.input_path
        if cfg.file_path:
            result = attachment.process_prompt_with_attachment(
                prompt_file=prompt_file,
                attachment_file=cfg.file_path,
                output_file=cfg.output_path,
                headless=HeadlessFlag(cfg.headless),
            )
        else:
            result = file_only.process_prompt_file_only(
                prompt_file=prompt_file,
                output_file=cfg.output_path,
                headless=HeadlessFlag(cfg.headless),
            )
    else:
        return error_response(RuntimeError(f"Unsupported CLI mode: {mode}"), "validation_error", "cli-400")

    failure = _processing_failure_message(result)
    if failure is not None:
        return error_response(RuntimeError(failure), "processing_failed", "cli-422")
    return success_response(result)


@safe_handle
def handle(
    args: object,
    cfg: AppConfig,
    direct: IDirectPromptAggregate,
    file_only: IPromptFileAggregate,
    attachment: IAttachmentPromptAggregate,
) -> dict[str, object]:
    """Dispatch single prompt processing to the matching pipeline orchestrator."""
    _ = args
    return dispatch_run(cfg, direct, file_only, attachment)
