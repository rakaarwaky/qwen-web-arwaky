"""ARCH-1-003: TUI typing protocol exists and declares mixin seams."""

from modules.tui.src.surface_tui_view_typing import QwenTuiAppLike


def test_protocol_declares_slot_seams() -> None:
    annotations = QwenTuiAppLike.__annotations__
    assert "_slot_workers" in annotations
    assert "_session" in annotations
    assert "_prompt" in annotations
    assert "_slot_cancel_events" in annotations
