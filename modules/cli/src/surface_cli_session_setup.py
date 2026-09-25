"""CLI surface: session setup submenu (SA-1).

The dead ``SessionSetupApp`` / ``run_session_setup`` entry points have been
removed.  ``SessionSetupScreen`` is now wired into the TUI login path:
``surface_cli_tui_handlers.action_login_action`` pushes this screen, which
gives the user a visible "Delete Session & Login Again" / "Back to Main Menu"
choice before the blocking ``setup_session()`` call runs in a background
worker.  ``ConfirmModal`` is the single source of truth in
``surface_cli_tui_components``.
"""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from modules.cli.src.surface_cli_tui_components import ConfirmModal


class SessionSetupScreen(Screen[None]):
    """Session setup submenu with status and actions.

    SA-1: wired into the TUI login flow.  ``on_login`` runs the interactive
    browser login in a background worker; ``on_back`` returns to the main TUI.
    """

    def __init__(
        self,
        status_text: str,
        on_login: Callable[[bool], None],
        on_back: Callable[[], None],
    ) -> None:
        """Initialise the screen.

        Args:
            status_text: Session status line shown at the top of the screen.
            on_login: Called with ``True`` when the user confirms the
                destructive "Delete Session & Login Again" action.
            on_back: Called when the user chooses to return to the main menu.
        """
        super().__init__()
        self._status_text = status_text
        self._on_login = on_login
        self._on_back = on_back

    def compose(self) -> ComposeResult:
        """Build the status line, action buttons, and footer."""
        yield Vertical(
            Static(self._status_text, id="session_status"),
            Button("Delete Session & Login Again", id="login", variant="error"),
            Button("Back to Main Menu", id="back"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route presses to the confirm-gated login flow or the back callback."""
        if event.button.id == "login":
            # U1 (CRITICAL): the ConfirmModal is the single gate — the user
            # must explicitly confirm "Delete Session & Login" before the
            # destructive path runs.

            def _on_confirm(confirmed: bool | None) -> None:
                if confirmed:
                    self._on_login(True)
                self.dismiss()

            self.app.push_screen(
                ConfirmModal(
                    "Confirm Session Reset",
                    "Are you sure you want to delete your saved browser session?\n"
                    "You will need to log in again manually.",
                    confirm_label="Delete Session & Login Again",
                ),
                _on_confirm,
            )
        elif event.button.id == "back":
            self._on_back()
            self.dismiss()


__all__ = ["SessionSetupScreen"]
