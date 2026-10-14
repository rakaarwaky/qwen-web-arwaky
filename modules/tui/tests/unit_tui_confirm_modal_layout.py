"""Unit tests for the destructive-action confirmation modal.

``ConfirmModal`` is the single gate for every destructive action in the TUI
(session delete, slot cancel, swarm fan-out, session-setup). These tests lock
the modal's geometry so it stays a centered dialog box in the terminal instead
of stretching to the full screen, and so the Cancel/Confirm buttons stay on
the dialog's center axis.
"""

from __future__ import annotations

import asyncio

from textual.app import App

from modules.tui.src.surface_tui_components import ConfirmModal
from modules.tui.src.surface_tui_css import TUI_CSS


class _ModalHost(App[None]):
    """Host app that applies the real TUI stylesheet and pushes the modal."""

    CSS = TUI_CSS

    def on_mount(self) -> None:
        self.push_screen(
            ConfirmModal(
                "Delete Session",
                "Delete 'arwaky007' from the pool and remove its browser profile?",
                confirm_label="Delete",
            )
        )


class TestConfirmModalCentering:
    """The confirm dialog renders as a centered box, not a full-screen fill."""

    def test_modal_box_is_centered_on_screen(self) -> None:
        """The dialog box sits at the center of the terminal with a margin
        around it on every side, so the confirmation reads as a dialog."""

        async def _run() -> None:
            app = _ModalHost()
            async with app.run_test(size=(80, 24)):
                modal = app.screen
                box = modal.query_one("#confirm-modal-container").region
                assert box.width < 80, f"modal spans the full width: {box}"
                assert box.height < 24, f"modal spans the full height: {box}"
                assert box.x > 0, f"modal is not centered horizontally: {box}"
                assert box.y > 0, f"modal is not centered vertically: {box}"
                assert box.right < 80, f"modal overflows the right edge: {box}"
                assert box.bottom < 24, f"modal overflows the bottom edge: {box}"

        asyncio.run(_run())

    def test_modal_buttons_are_centered_in_the_box(self) -> None:
        """Cancel and Delete sit on the dialog's center axis."""

        async def _run() -> None:
            app = _ModalHost()
            async with app.run_test(size=(80, 24)):
                box = app.screen.query_one("#confirm-modal-container").region
                buttons = {b.id: b.region for b in app.screen.query("#confirm-btn-row Button")}
                assert set(buttons) == {"btn-cancel", "btn-confirm"}
                for button_id, region in buttons.items():
                    assert region.center[0] == box.center[0], f"{button_id} is not centered in the dialog: {region}"

        asyncio.run(_run())
