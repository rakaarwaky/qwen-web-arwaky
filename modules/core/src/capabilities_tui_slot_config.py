"""Capability layer (capabilities_tui_slot_config): resolve TUI slot inputs to AppConfig.

Implements ITuiSlotConfigProtocol.

Keeps domain/control logic (role-template materialization, path resolution,
attachment-stem output naming with mandatory timestamp) out of the passive
TUI surface. The TUI only reads widget values and delegates here.
"""

from __future__ import annotations

from pathlib import Path

from modules.core.src.utility_core_config_factory import (
    build_app_config,
    resolve_pipeline_output_path,
)
from modules.shared.src.contract_core_protocol import ITuiSlotConfigProtocol
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    OutputPath,
    PromptText,
    SlotInputValue,
    SlotRunPlan,
)
from modules.shared.src.utility_core_prompt_template import is_prompt_role, materialize_role_template

# Backward-compatible aliases — the concrete types now live in the taxonomy
# layer so the contract can name them without importing Capabilities.
SlotInputError: type[SlotInputValue] = SlotInputValue


class TuiSlotConfigResolver(ITuiSlotConfigProtocol):
    """Resolve raw TUI slot widget values into an executable run plan."""

    def resolve_slot_run_plan(
        self,
        prompt_val: PromptText,
        file_val: PromptText,
        output_val: OutputPath,
        headless: HeadlessFlag,
    ) -> SlotRunPlan | SlotInputValue:
        """Validate widget values and build the AppConfig for a slot run.

        The output filename prefers the attachment stem when an attachment is
        given, otherwise the prompt stem; a timestamp suffix is always applied.
        """
        prompt_stripped = prompt_val.strip()
        if not prompt_stripped:
            return SlotInputValue("Prompt file is required.")

        if is_prompt_role(prompt_stripped):
            p_path = materialize_role_template(prompt_stripped)
        else:
            p_path = Path(prompt_stripped).resolve()
            if not p_path.exists():
                return SlotInputValue(f"File not found: {prompt_stripped}")

        file_stripped = file_val.strip()
        f_path = Path(file_stripped).resolve() if file_stripped else None

        out_stripped = str(output_val).strip()
        _, out_path = resolve_pipeline_output_path(
            p_path,
            output_file=Path(out_stripped).resolve() if out_stripped else None,
            attachment_path=f_path,
        )

        cfg = build_app_config(
            mode="single",
            input_path=p_path,
            output_path=out_path,
            prompt_file=p_path,
            prompt_path=p_path,
            file_path=f_path,
            headless=headless,
            request_timeout=120,
        )
        return SlotRunPlan(prompt_path=p_path, attachment_path=f_path, config=cfg)

    def discover_batch_prompts(self, batch_dir: FilePath) -> list[Path] | SlotInputValue:
        """Return sorted .md prompt files inside a batch directory.

        Returns a SlotInputValue describing the problem when the directory is
        missing or empty, so the surface layer only forwards the message.
        """
        raw_dir = str(batch_dir)
        if not raw_dir.strip():
            return SlotInputValue("Please specify a directory path.")
        batch_path = Path(raw_dir).expanduser().resolve()
        if not batch_path.is_dir():
            return SlotInputValue(f"Directory not found: {batch_path}")
        files = sorted(batch_path.glob("*.md"))
        if not files:
            return SlotInputValue(f"No .md files found in {batch_path}")
        return files


__all__ = ["SlotInputError", "SlotRunPlan", "TuiSlotConfigResolver"]
