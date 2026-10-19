"""CLI surface: run command — single prompt processing dispatch.

Smart surface: maps parsed args/config to the prompt aggregate based on
AppConfig.mode, then delegates with zero business logic.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from modules.shared.src.common.taxonomy_core_vo import AppConfig, HeadlessFlag, PromptText
from modules.shared.src.common.utility_response_normalizer import (
    detect_processing_failure,
    safe_handle,
    success_response,
)
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest


def _processing_failure_message(result: object) -> str | None:
    """Return a failure reason when a normal core response reports failed work."""
    return detect_processing_failure(result)


def dispatch_run(
    cfg: AppConfig,
    prompt: IPromptAggregate,
    session_resolver: Callable[[], Path | None] | None = None,
) -> dict[str, object]:
    """C4: single shared dispatcher for direct/single modes.

    Used by both ``handle`` (run subcommand) and ``InteractiveController.run``
    so the dispatch semantics stay in exactly one place.

    ``session_resolver`` returns the pool session path chosen by session
    rotation so the direct pipeline can use it; ``build_app_config`` inside
    the adapter builds a fresh AppConfig, so without the resolver the pool
    selection would be dropped and the default session used.
    """
    mode = cfg.mode

    if mode == "direct":
        raw_prompt = cfg.inline_prompt_text
        if not raw_prompt:
            return {
                "success": False,
                "message": "Missing inline prompt text for direct mode.",
                "error_code": "cli-400",
            }
        prompt_text = PromptText(raw_prompt)
        response = prompt.execute(
            PromptRequest(
                verb="process_direct_prompt",
                prompt=prompt_text,
                output_file=cfg.output_path,
                headless=HeadlessFlag(cfg.headless),
                session_resolver=session_resolver,
            )
        )
        result = response.response_text
    elif mode == "single":
        prompt_file = cfg.prompt_path or cfg.input_path
        if cfg.file_path:
            response = prompt.execute(
                PromptRequest(
                    verb="process_prompt_with_attachment",
                    prompt_file=prompt_file,
                    attachment_file=cfg.file_path,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                    session_resolver=session_resolver,
                )
            )
        else:
            response = prompt.execute(
                PromptRequest(
                    verb="process_prompt_file_only",
                    prompt_file=prompt_file,
                    output_file=cfg.output_path,
                    headless=HeadlessFlag(cfg.headless),
                    session_resolver=session_resolver,
                )
            )
        result = response.response_text
    else:
        return {
            "success": False,
            "message": f"Unsupported CLI mode: {mode}",
            "error_code": "cli-400",
        }

    failure = _processing_failure_message(result)
    if failure is not None:
        return {"success": False, "message": failure, "error_code": "cli-422"}
    return success_response(result)


@safe_handle
def handle(
    args: object,
    cfg: AppConfig,
    prompt: IPromptAggregate,
    session_resolver: Callable[[], Path | None] | None = None,
) -> dict[str, object]:
    """Dispatch single prompt processing to the prompt aggregate pipeline."""
    _ = args
    return dispatch_run(cfg, prompt, session_resolver=session_resolver)


__all__ = ["dispatch_run", "handle"]
