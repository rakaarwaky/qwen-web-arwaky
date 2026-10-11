"""Regression tests for the FilePickerModal/HelpScreen Toast+MouseDown crash.

Textual's Screen._forward_event builds a text-selection SelectStart whose
container is resolved from the widget under the cursor when the modal's
ToastRack shows a visible warning Toast. The Toast's parent (a ToastHolder,
0x0 region inside the rack) can be removed in the same frame the MouseDown
is dispatched (ToastRack.show() prunes toasts not present in the current
notification list), which leaves no MapGeometry for the container and
crashes with ``AttributeError: 'NoneType' object has no attribute 'region'``.

FilePickerModal and HelpScreen override ``ALLOW_SELECT = False`` so the
MouseDown branch never builds that SelectStart while the modal is open,
which is the root-cause fix (these pickers never need text selection).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.events import MouseDown
from textual.widgets import Button, Label
from textual.widgets._toast import Toast

from modules.cli.src.surface_cli_tui_components import FilePickerModal, HelpScreen


def test_file_picker_modal_disables_text_selection() -> None:
    assert FilePickerModal.ALLOW_SELECT is False


def test_help_screen_disables_text_selection() -> None:
    assert HelpScreen.ALLOW_SELECT is False


def test_mouse_down_on_toast_does_not_crash_in_file_picker() -> None:
    """Reproduce the crash scenario: a warning Toast is visible while the
    FilePickerModal is open, the user's MouseDown lands on the Toast, and
    the Toast's holder is pruned in the same frame. Must not raise."""

    class HostApp(App):
        def __init__(self) -> None:
            super().__init__()
            self._picker: FilePickerModal | None = None

        def compose(self) -> ComposeResult:
            with Vertical():
                yield Label("host")
                yield Button("open", id="btn-open")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn-open":
                self._picker = FilePickerModal(start_path=Path.cwd())
                self.push_screen(self._picker)

    app = HostApp()

    async def _run() -> None:
        async with app.run_test(size=(80, 24), notifications=True) as pilot:
            await pilot.click("#btn-open")
            await pilot.pause()
            assert isinstance(app.screen, FilePickerModal)
            picker = app.screen

            # Emit a warning toast while the picker is the active screen.
            app.notify("Jobs aggregate not available in this container.", severity="warning")
            await pilot.pause(0.3)

            toast = picker.query(Toast).first()
            region = toast.region

            # Prune the holder in the same frame, mimicking ToastRack.show()
            # refreshing the rack and dropping the just-removed toast.
            holder = toast.parent
            assert holder is not None
            holder.remove()
            await pilot.pause()

            # Dispatch the MouseDown exactly where the Toast used to be.
            x, y = region.x + 1, region.y + 1
            event = MouseDown(picker, x, y, 0, 0, 1, False, False, False)
            picker.post_message(event)
            await pilot.pause(0.3)

            # No crash; the selection state must remain None (select is disabled).
            assert picker._select_state is None

    asyncio.run(_run())


def test_mouse_down_on_toast_does_not_crash_in_help_screen() -> None:
    """Same crash guard for the HelpScreen overlay, which shares the
    modal+ToastRack interaction with FilePickerModal."""

    class HostApp(App):
        def __init__(self) -> None:
            super().__init__()

        def compose(self) -> ComposeResult:
            with Vertical():
                yield Label("host")
                yield Button("open", id="btn-open")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn-open":
                self.push_screen(HelpScreen(num_slots=4))

    app = HostApp()

    async def _run() -> None:
        async with app.run_test(size=(80, 24), notifications=True) as pilot:
            await pilot.click("#btn-open")
            await pilot.pause()
            assert isinstance(app.screen, HelpScreen)
            help_screen = app.screen

            app.notify("Session check: warning", severity="warning")
            await pilot.pause(0.3)

            toasts = list(help_screen.query(Toast))
            if not toasts:
                # The help overlay's rack may not have materialised the toast
                # yet; the ALLOW_SELECT guard still applies unconditionally.
                assert help_screen.ALLOW_SELECT is False
                return

            toast = toasts[0]
            region = toast.region
            holder = toast.parent
            assert holder is not None
            holder.remove()
            await pilot.pause()

            x, y = region.x + 1, region.y + 1
            event = MouseDown(help_screen, x, y, 0, 0, 1, False, False, False)
            help_screen.post_message(event)
            await pilot.pause(0.3)

            assert help_screen._select_state is None

    asyncio.run(_run())
