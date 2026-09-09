"""CLI surface: Textual-based Session Setup submenu."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Static


class ConfirmModal(ModalScreen[bool]):
    """Modal screen asking confirmation for destructive actions."""

    BINDINGS = [
        Binding("escape", "dismiss_no", "Cancel"),
        Binding("n", "dismiss_no", "Cancel", show=False),
        Binding("y", "dismiss_yes", "Confirm", show=False),
    ]

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-modal-container"):
            yield Static(f"[bold red]{self._title.upper()}[/bold red]\n\n{self._message}\n")
            yield Button("Cancel", id="btn-cancel", variant="default")
            yield Button("Delete Session & Login", id="btn-confirm", variant="error")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_dismiss_no(self) -> None:
        self.dismiss(False)

    def action_dismiss_yes(self) -> None:
        self.dismiss(True)


class SessionSetupScreen(Screen["SessionSetupApp"]):
    """Session setup submenu with status and actions."""

    def __init__(self, status_text: str, on_login: Callable[[], None], on_back: Callable[[], None]) -> None:
        super().__init__()
        self.status_text = status_text
        self.on_login = on_login
        self.on_back = on_back

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.status_text, id="session_status"),
            Button("Delete Session & Login Again", id="login", variant="error"),
            Button("Back to Main Menu", id="back"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login":

            def _on_confirm(confirmed: bool | None) -> None:
                if confirmed:
                    self.on_login()
                    self.app.exit("login")

            msg = "Are you sure you want to delete your saved browser session?\nYou will need to log in again manually."
            self.app.push_screen(ConfirmModal("Confirm Session Reset", msg), _on_confirm)
        elif event.button.id == "back":
            self.on_back()
            self.app.exit("back")


class SessionSetupApp(App[str]):
    """Textual app for session setup submenu."""

    CSS = """
    $border: #464554;

    Screen {
        align: center middle;
    }
    Vertical {
        width: auto;
        min-width: 40;
        max-width: 70;
        height: auto;
        border: solid $border;
        padding: 1 2;
    }
    #session_status {
        width: 100%;
        margin-bottom: 1;
    }
    Button {
        width: 100%;
        margin: 1 0;
    }
    """

    def __init__(self, status_text: str, on_login: Callable[[], None], on_back: Callable[[], None]) -> None:
        super().__init__()
        self.status_text = status_text
        self.on_login = on_login
        self.on_back = on_back

    def on_mount(self) -> None:
        self.push_screen(SessionSetupScreen(self.status_text, self.on_login, self.on_back))

    # U1 (CRITICAL): the app-level on_button_pressed handler was REMOVED.
    # Button.Pressed events bubble from the screen to the app, so the old
    # duplicate handler fired alongside SessionSetupScreen's handler and
    # invoked on_login() immediately — bypassing the ConfirmModal and
    # deleting the session without confirmation (violated FR-002.4).
    # The screen is now the single event handler; the modal is the only gate.


def run_session_setup(status_text: str, on_login: Callable[[], None], on_back: Callable[[], None]) -> str:
    """Run the Textual session setup submenu and return the selected action."""
    app = SessionSetupApp(status_text, on_login, on_back)
    # C3: screen-driven exits call self.app.exit("login"/"back"), which lands
    # in app.run()'s return value — NOT app.result. Validate it here.
    result = app.run()
    return result if result in {"login", "back"} else "back"
