"""Shared QwenTuiApp harness for TUI surface unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
from modules.tui.src.surface_tui_app_screen import QwenTuiApp


def make_app(*, with_prompt_mock: bool = False) -> QwenTuiApp:
    """Build a mounted-ready QwenTuiApp with MagicMock collaborators."""
    prompt = MagicMock()
    if with_prompt_mock:
        prompt.execute.return_value = MagicMock(response_text="ok")
    return QwenTuiApp(
        workspace=MagicMock(),
        prompt=prompt,
        slot_config=SlotRunPlanResolver(),
        session=MagicMock(),
        jobs=MagicMock(),
        updater=MagicMock(),
        job_storage=MagicMock(),
    )


__all__ = ["make_app"]
