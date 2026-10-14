"""Unit tests for the TUI modal dialog geometry.

Every modal the TUI opens must render as a centered dialog box with a frame,
not a full-screen fill with children stacked at the left edge. This file locks
the two modals fixed alongside ``ConfirmModal`` (see
``unit_tui_confirm_modal_layout.py``): the add-session dialog and the prompt
template picker.

Covered pop-ups:
- ``AddSessionModal`` (ctrl+l / session-setup)
- ``TemplatePickerModal`` (the Templates pill on the chat console)
"""

from __future__ import annotations

import asyncio

from textual.app import App
from textual.screen import ModalScreen

from modules.tui.src.surface_tui_components import AddSessionModal, TemplatePickerModal
from modules.tui.src.surface_tui_css import TUI_CSS

_OPTIONS = [
    ("Default", "default"),
    ("Code Reviewer", "reviewer"),
    ("Summarizer", "summarizer"),
]


class _ModalHost(App[None]):
    """Host app that applies the real TUI stylesheet and pushes the modal."""

    CSS = TUI_CSS

    def __init__(self, modal: ModalScreen[object]) -> None:
        super().__init__()
        self._modal = modal

    def on_mount(self) -> None:
        self.push_screen(self._modal)


def _assert_centered_box(screen: object, box_id: str, width: int, height: int) -> None:
    box = screen.query_one(box_id).region
    assert box.width < width, f"modal spans the full width: {box}"
    assert box.height < height, f"modal spans the full height: {box}"
    assert box.x > 0, f"modal is not centered horizontally: {box}"
    assert box.y > 0, f"modal is not centered vertically: {box}"
    assert box.right < width, f"modal overflows the right edge: {box}"
    assert box.bottom < height, f"modal overflows the bottom edge: {box}"


class TestAddSessionModalCentering:
    """The add-session dialog renders as a centered box."""

    def test_modal_box_is_centered_on_screen(self) -> None:
        """The dialog box sits at the center of the terminal, not a
        full-screen fill."""

        async def _run() -> None:
            app = _ModalHost(AddSessionModal())
            async with app.run_test(size=(80, 24)):
                _assert_centered_box(app.screen, "#add-session-container", 80, 24)

        asyncio.run(_run())

    def test_modal_children_are_centered_in_the_box(self) -> None:
        """The Start Login / Cancel button group sits on the dialog's
        center axis."""

        async def _run() -> None:
            app = _ModalHost(AddSessionModal())
            async with app.run_test(size=(80, 24)):
                box = app.screen.query_one("#add-session-container").region
                buttons = list(app.screen.query("#add-session-btn-row Button"))
                assert {b.id for b in buttons} == {"btn-start-login", "btn-cancel"}
                row = buttons[0].region.union(buttons[1].region)
                group_center = row.center[0]
                # Textual aligns to whole cells, so the group center can sit
                # half a cell off the box center for odd-width groups.
                assert abs(group_center - box.center[0]) <= 0.5, f"button group is not centered in the dialog: {row}"

        asyncio.run(_run())


class TestTemplatePickerModalCentering:
    """The prompt-template picker renders as a centered box."""

    def test_modal_box_is_centered_on_screen(self) -> None:
        """The picker box sits at the center of the terminal, not pinned
        to the left edge."""

        async def _run() -> None:
            app = _ModalHost(TemplatePickerModal(_OPTIONS))
            async with app.run_test(size=(80, 24)):
                _assert_centered_box(app.screen, "#template-picker-container", 80, 24)

        asyncio.run(_run())

    def test_modal_buttons_are_centered_in_the_box(self) -> None:
        """Every role button sits on the dialog's center axis."""

        async def _run() -> None:
            app = _ModalHost(TemplatePickerModal(_OPTIONS))
            async with app.run_test(size=(80, 24)):
                box = app.screen.query_one("#template-picker-container").region
                for button in app.screen.query("#tpl-btn-row Button"):
                    assert button.region.center[0] == box.center[0], (
                        f"{button.id} is not centered in the dialog: {button.region}"
                    )

        asyncio.run(_run())
