"""Screen actions and handler helpers for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing the ``action_*`` methods
(keyboard bindings, tab navigation, copy, quit) plus the screen-level button
helpers for the swarm, auth, account, and chat-console controls. The widget
``on_*`` callbacks that route those controls live in
:class:`~modules.cli.src.surface_cli_tui_events._TuiEventsMixin`.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual import work
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Select, TabbedContent

from modules.cli.src.surface_cli_session_setup import SessionSetupScreen
from modules.cli.src.surface_cli_tui_components import ConfirmModal, FilePickerModal, HelpScreen, QwenTuiRichLog
from modules.cli.src.surface_cli_tui_css import THEME

# The dock's active marker: a short accent bar centred over the active
# section, the way the mockup draws it.
NAV_ACTIVE_MARKER = "━━━"


class _TuiHandlersMixin:
    """Mixin that owns all Textual event handlers and action bindings."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _target_field_for_picker: str | None
    _template_roles: set[str]
    _slot_workers: dict[int, Any]
    _NUM_SLOTS: int
    _run_swarm: Any
    _cancel_swarm: Any
    _sessions_cache: list[Any]
    _sessions_loaded_once: bool

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _run_slot: Any
    _cancel_slot: Any
    _show_settings_section: Any
    _append_chat_message: Any
    _run_composer_slot: Any
    query: Any
    query_one: Any
    _log_swarm_msg: Any
    set_focus: Any
    _log_msg: Any
    copy_to_clipboard: Any
    push_screen: Any
    _login_worker: Any
    _workspace: Any
    exit: Any
    _login_in_flight: bool
    call_from_thread: Any
    notify: Any
    _session: Any
    _session_manager: Any
    _refresh_sessions_table: Any
    _run_session_health_check: Any
    _render_account_cards: Any

    def _swarm_button_pressed(self, button_id: str) -> None:
        """Route Swarm-screen button presses to the right handler."""
        if button_id == "btn-swarm-start":
            self._run_swarm()
        elif button_id == "btn-swarm-cancel":
            self._cancel_swarm()
        elif button_id == "btn-browse-swarm-file":
            self._open_picker("input-swarm-file", select_directories=True)
        elif button_id in ("btn-swarm-event", "btn-swarm-system"):
            self._show_swarm_log(button_id == "btn-swarm-system")
        elif button_id == "btn-clear-swarm-log":
            self._clear_swarm_log()

    def _apply_template_chip(self, button_id: str) -> None:
        """Route a template-chip press into the slot's Select widget.

        The chip id encodes both the slot and the role (``chip-<slot>-<role>``).
        Selecting the same role twice is a no-op so the chip does not emit a
        redundant log line on a repeated press.
        """
        _, _, remainder = button_id.partition("chip-")
        slot_raw, _, role = remainder.partition("-")
        if not slot_raw.isdigit() or not role:
            return
        slot_id = int(slot_raw)
        with contextlib.suppress(NoMatches):
            select = self.query_one(f"#select-template-{slot_id}", Select)
            if select.value == role:
                return
            select.value = role

    def _show_swarm_log(self, show_system: bool) -> None:
        """Switch the Swarm tab between the Event log and the System log.

        The mockup presents these as a segmented toggle over one panel, so
        exactly one of the two RichLog views stays visible and the toggle
        buttons carry matching active/inactive styling.
        """
        with contextlib.suppress(NoMatches):
            event_log = self.query_one("#log-view-swarm", QwenTuiRichLog)
            system_log = self.query_one("#log-view-swarm-system", QwenTuiRichLog)
            event_log.display = not show_system
            system_log.display = show_system
        with contextlib.suppress(NoMatches):
            event_btn = self.query_one("#btn-swarm-event", Button)
            system_btn = self.query_one("#btn-swarm-system", Button)
            # Add/remove one class at a time. set_classes() would also drop
            # the -style-default class that Textual's own Button CSS hangs
            # its default rendering off, leaving the button unstyled.
            event_btn.set_class(not show_system, "toggle-active")
            event_btn.set_class(show_system, "toggle-inactive")
            system_btn.set_class(show_system, "toggle-active")
            system_btn.set_class(not show_system, "toggle-inactive")

    def _clear_swarm_log(self) -> None:
        """Empty whichever Swarm log view is currently on screen."""
        with contextlib.suppress(NoMatches):
            system_visible = self.query_one("#log-view-swarm-system", QwenTuiRichLog).display
            view = self.query_one("#log-view-swarm-system" if system_visible else "#log-view-swarm", QwenTuiRichLog)
            view.clear()
            self._log_swarm_msg(
                "[{}]Swarm log cleared.[/]".format(THEME["muted"]),
            )

    def _account_button_pressed(self, action: str, position: int) -> None:
        """Handle an action on the Sessions pane's account card at *position*."""
        cache: list[Any] = getattr(self, "_sessions_cache", [])
        session = cache[position - 1] if 0 < position <= len(cache) else None
        name = str(getattr(session, "name", "") or f"session {position}")
        if action == "test":
            # The pool health check is the only real connectivity probe this
            # build has, so one card's TEST runs it rather than inventing a
            # single-session result from the last stored state.
            self._log_msg("[bold {}]TEST:[/] Checking connection for {}.".format(THEME["accent_fg"], escape(name)))
            self._run_session_health_check()
            return
        # Disconnecting drops the stored auth session. That is an approved-
        # only operation, so the card points at the CLI command instead of
        # doing it from the UI.
        self.notify(
            f"Run 'qwa sessions remove --name {name}' to disconnect.",
            title="Disconnect",
            severity="information",
        )

    def _ensure_sessions_loaded(self) -> None:
        """Fetch the account pool the first time the Sessions pane is opened."""
        if getattr(self, "_sessions_loaded_once", False) or getattr(self, "_session_manager", None) is None:
            return
        self._sessions_loaded_once = True
        self._refresh_sessions_table()

    def _auth_panel_pressed(self, button_id: str) -> None:
        """Handle the Login screen's auth-panel buttons.

        ``btn-session-add`` toggles the expandable panel;
        ``btn-auth-connect`` / ``btn-auth-cancel`` close it (and
        ``btn-auth-connect`` also fires the login flow).
        """
        with contextlib.suppress(NoMatches):
            panel = self.query_one("#auth-panel", Vertical)
            if button_id == "btn-session-add":
                panel.display = not panel.display
            else:
                panel.display = False
                if button_id == "btn-auth-connect":
                    self.action_login_action()

    # ── File picker ──────────────────────────────────────────────────────

    def _open_picker(self, target_input_id: str, select_directories: bool = False) -> None:
        # C3: capture the target id in the closure so concurrent picker
        # pushes cannot overwrite each other via shared instance state.
        captured_target = target_input_id
        return_focus_id = f"btn-browse-{target_input_id.removeprefix('input-')}"

        def _on_picked(path: str | None) -> None:
            if path and captured_target:
                with contextlib.suppress(NoMatches):
                    field = self.query_one(f"#{captured_target}", Input)
                    field.value = path

        self.push_screen(
            FilePickerModal(
                select_directories=select_directories,
                return_focus_id=return_focus_id,
            ),
            _on_picked,
        )

    # ── Tab navigation helpers ───────────────────────────────────────────

    def _get_active_slot_id(self) -> int:
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            active_id = tabs.active or ""
            if active_id.startswith("tab-slot-"):
                return int(active_id.split("-")[-1])
        return 1

    def _refresh_nav_dock(self) -> None:
        """Update the bottom nav dock's active indicator to match the tab bar."""
        with contextlib.suppress(Exception):
            from textual.widgets import Button

            tabs = self.query_one(TabbedContent)
            active = tabs.active or ""
            overview_btn = self.query_one("#nav-overview", Button)
            login_btn = self.query_one("#nav-login", Button)
            chat_btn = self.query_one("#nav-chat", Button)
            swarm_btn = self.query_one("#nav-swarm", Button)
            settings_btn = self.query_one("#nav-settings", Button)
            # Reset all to inactive; then activate the one that matches. The
            # active rule must drop the inactive class too: both classes on one
            # button makes the later-defined inactive rule win.
            for btn in (overview_btn, login_btn, chat_btn, swarm_btn, settings_btn):
                btn.set_class(True, "nav-inactive")
                btn.set_class(False, "nav-active")
            active_btn = {
                "tab-overview": overview_btn,
                "tab-sessions": login_btn,
                "tab-swarm": swarm_btn,
                "tab-settings": settings_btn,
            }.get(active)
            if active.startswith("tab-slot-"):
                active_btn = chat_btn
            if active_btn is not None:
                active_btn.set_class(False, "nav-inactive")
                active_btn.set_class(True, "nav-active")
            self._refresh_nav_marker(active)

    def _refresh_nav_marker(self, active_tab: str) -> None:
        """Move the dock's accent bar over the cell that is now active.

        The mockup marks the active section with a short bar centred above
        its icon rather than a hairline across the whole cell, so the bar
        lives in its own strip whose 1fr cells line up with the buttons.
        """
        with contextlib.suppress(Exception):
            bars = {
                "tab-overview": "#nav-bar-overview",
                "tab-sessions": "#nav-bar-login",
                "tab-swarm": "#nav-bar-swarm",
                "tab-settings": "#nav-bar-settings",
            }
            slot_tab = active_tab.startswith("tab-slot-")
            target = bars.get(active_tab, "#nav-bar-chat" if slot_tab else None)
            for bar in self.query(".nav-bar"):
                is_target = f"#{bar.id}" == target
                bar.set_class(is_target, "nav-bar-active")
                bar.update(NAV_ACTIVE_MARKER if is_target else "")

    def _nav_dock_go(self, button_id: str) -> None:
        """Switch the tab bar to whichever section a bottom nav item points at.

        CHAT has no single tab of its own: it stands for every per-slot job
        tab, so it lands on the slot the user is already on (slot 1 when the
        active tab is not a slot tab). SETTINGS follows the same rule — it
        opens on whichever slot is currently on screen.
        """
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            if button_id == "nav-overview":
                tabs.active = "tab-overview"
            elif button_id == "nav-login":
                tabs.active = "tab-sessions"
                self._ensure_sessions_loaded()
            elif button_id == "nav-chat":
                active_id = tabs.active or ""
                tabs.active = active_id if active_id.startswith("tab-slot-") else "tab-slot-1"
            elif button_id == "nav-swarm":
                tabs.active = "tab-swarm"
            elif button_id == "nav-settings":
                self.action_switch_tab_settings()
                return
        self._refresh_nav_dock()

    # ── Keyboard actions ─────────────────────────────────────────────────

    def action_run_active_slot(self) -> None:
        """Run the currently focused slot from the keyboard (enter / ctrl+r)."""
        self._run_slot(self._get_active_slot_id())

    def action_cancel_active_slot(self) -> None:
        """A8: cancel the currently focused slot from the keyboard (ctrl+x)."""
        self._cancel_slot(self._get_active_slot_id())

    def action_copy_active_log(self) -> None:
        """Copy the currently visible log buffer to the system clipboard.

        Targets whichever log view belongs to the active tab: the overview
        log when the Overview tab is focused, the swarm log when the Swarm
        tab is focused, or the per-slot log view when a slot tab is active.
        """
        active_view: QwenTuiRichLog | None = None
        log_views: dict[Any, Any] = getattr(self, "_log_views", {})
        active_key = self._get_active_slot_id()
        if active_key == 0:
            active_view = log_views.get(0)
        elif active_key == -1:
            active_view = log_views.get(-1)
        else:
            active_view = log_views.get(active_key)

        if active_view is None:
            self._log_msg("[yellow]No log view available to copy.[/]")
            return

        text = active_view.copy_text()
        if not text:
            self._log_msg("[yellow]Log buffer is empty — nothing to copy.[/]")
            return

        self.copy_to_clipboard(text)
        self.notify(f"Copied {len(text.splitlines())} log lines to clipboard", severity="information")

    def _copy_log_by_id(self, button_id: str) -> None:
        """Copy the log view associated with a copy button on the Overview/Swarm tab."""
        log_views: dict[Any, Any] = getattr(self, "_log_views", {})
        view = log_views.get(0) if button_id == "btn-copy-log" else log_views.get(-1)
        if view is None:
            self._log_msg("[yellow]No log view available to copy.[/]")
            return
        self._copy_rich_log(view)

    def _copy_slot_log(self, slot_id: int) -> None:
        """Copy whichever of the slot's two log buffers is on screen."""
        log_views: dict[Any, Any] = getattr(self, "_log_views", {})
        system_views: dict[Any, Any] = getattr(self, "_system_log_views", {})
        view = log_views.get(slot_id)
        system_view = system_views.get(slot_id)
        if view is not None and not view.display:
            view = None
        if system_view is not None and not system_view.display:
            system_view = None
        target = view or system_view
        if target is None:
            self._log_msg(f"[yellow]Slot {slot_id} log view not found.[/]")
            return
        self._copy_rich_log(target)

    def _copy_rich_log(self, view: QwenTuiRichLog) -> None:
        text = view.copy_text()
        if not text:
            self._log_msg("[yellow]Log buffer is empty — nothing to copy.[/]")
            return
        self.copy_to_clipboard(text)
        self.notify(f"Copied {len(text.splitlines())} log lines to clipboard", severity="information")

    def action_switch_tab_overview(self) -> None:
        """Switch to the Overview tab (alt+0)."""
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-overview"
        self._refresh_nav_dock()

    def action_switch_tab_swarm(self) -> None:
        """Switch to the Swarm tab (ctrl+alt+s)."""
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-swarm"
        self._refresh_nav_dock()

    def action_switch_tab_settings(self) -> None:
        """Switch to the Settings tab (ctrl+comma), keeping the slot on screen.

        Arriving from another tab picks the slot the user was just looking at;
        pressing the shortcut while already on Settings leaves the configured
        slot alone instead of snapping back to slot 1.
        """
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            if tabs.active != "tab-settings":
                self._show_slot_config(self._get_active_slot_id())
                tabs.active = "tab-settings"
        self._refresh_nav_dock()

    def _switch_to_slot(self, slot_id: int) -> None:
        """Show a slot's tab and carry the keyboard focus into it.

        Clicking a pill focuses that pill, and Textual reacts to a focus
        landing in a pane by making THAT pane the active tab — which undid
        the switch and sent the console back to the slot the click came from.
        Moving the focus into the new pane keeps the tab and the focus in
        step, so one click lands and the keyboard follows.
        """
        with contextlib.suppress(Exception):
            tabs = self.query_one(TabbedContent)
            tab_id = f"tab-slot-{slot_id}"
            tabs.active = tab_id
            pane = tabs.get_pane(tab_id)
            focusable = [widget for widget in pane.query("*") if widget.focusable]
            self.set_focus(focusable[0] if focusable else None, scroll_visible=False)
        self._refresh_nav_dock()

    # ── Chat console / Settings pane ─────────────────────────────────────

    def _show_slot_log(self, slot_id: int, show_system: bool) -> None:
        """Swap a chat console between the slot's Event log and System log.

        The two share one panel, so exactly one view stays visible and only
        the pressed button keeps the active fill.
        """
        with contextlib.suppress(NoMatches):
            self.query_one(f"#log-view-{slot_id}", QwenTuiRichLog).display = not show_system
            self.query_one(f"#log-view-{slot_id}-system", QwenTuiRichLog).display = show_system
        with contextlib.suppress(NoMatches):
            event_btn = self.query_one(f"#btn-slot-event-{slot_id}", Button)
            system_btn = self.query_one(f"#btn-slot-system-{slot_id}", Button)
            event_btn.set_class(show_system, "seg-active")
            system_btn.set_class(not show_system, "seg-active")

    def _show_slot_config(self, slot_id: int) -> None:
        """Display one slot's configuration block and mark its picker pill."""
        for s in range(1, self._NUM_SLOTS + 1):
            with contextlib.suppress(NoMatches):
                self.query_one(f"#slot-config-{s}", Vertical).display = s == slot_id
            with contextlib.suppress(NoMatches):
                self.query_one(f"#cfg-slot-{s}", Button).set_class(s == slot_id, "slot-chip-active")

    def _goto_slot_settings(self, slot_id: int) -> None:
        """Open the Settings pane on *slot_id*'s form — the Templates pill."""
        # The form is one of two Settings sections; arriving from the chat
        # console while the overrides card is open must switch back to it.
        self._show_settings_section(False)
        self._show_slot_config(slot_id)
        with contextlib.suppress(Exception):
            self.query_one(TabbedContent).active = "tab-settings"
        self._refresh_nav_dock()

    def _send_composer(self, slot_id: int) -> None:
        """Echo the typed task into the transcript and dispatch it."""
        text = ""
        with contextlib.suppress(NoMatches):
            composer = self.query_one(f"#composer-{slot_id}", Input)
            text = composer.value.strip()
            if text:
                composer.value = ""
        if not text:
            with contextlib.suppress(Exception):
                self.notify(
                    "Type a task before sending.",
                    severity="warning",
                    title=f"Slot {slot_id}",
                )
            return
        attachment = ""
        with contextlib.suppress(NoMatches):
            attachment = self.query_one(f"#input-file-{slot_id}", Input).value.strip()
        self._append_chat_message(slot_id, "user", text, attachment=attachment)
        self._run_composer_slot(slot_id, text)

    def action_switch_tab_slot(self, slot_id: int) -> None:
        """Switch to the tab of *slot_id* (alt+1..9, ctrl+alt+0..9)."""
        self._switch_to_slot(int(slot_id))

    def action_prev_slot(self) -> None:
        """A4: navigate to the previous slot tab (alt+left)."""
        current = self._get_active_slot_id()
        prev = current - 1 if current > 1 else self._NUM_SLOTS
        self._switch_to_slot(prev)

    def action_next_slot(self) -> None:
        """A4: navigate to the next slot tab (alt+right)."""
        current = self._get_active_slot_id()
        nxt = current + 1 if current < self._NUM_SLOTS else 1
        self._switch_to_slot(nxt)

    def action_show_help(self) -> None:
        """A4: push the keyboard-shortcut reference overlay."""
        self.push_screen(HelpScreen(self._NUM_SLOTS))

    def action_login_action(self) -> None:
        """Open the session-setup submenu guarding the destructive login flow."""
        # U3: re-entrancy guard — one login flow at a time.
        if getattr(self, "_login_in_flight", False):
            self._log_msg("[bold {}]WARNING:[/] Login already in progress.".format(THEME["warn"]))
            return

        # SA-1: wire the previously-dead SessionSetupScreen into the TUI login
        # path.  Show the session-setup submenu; "Delete Session & Login
        # Again" triggers the blocking setup_session() worker after
        # confirmation, "Back to Main Menu" dismisses the screen.
        self._log_msg("[bold {}]>>> Opening session setup menu...[/]".format(THEME["accent_fg"]))
        self.push_screen(
            SessionSetupScreen(
                status_text=f"[bold]Session status: {self._session_badge_text()}[/]",
                on_login=self._start_login_worker,
                on_back=lambda: self._log_msg(
                    "[{}]Session setup cancelled — back to main menu.[/]".format(THEME["muted"])
                ),
            )
        )

    def _session_badge_text(self) -> str:
        """Return a short session status string for the setup screen."""
        if self._session is None:
            return "N/A (no session orchestrator)"
        last = getattr(self, "_last_session_state", None)
        if last:
            return f"{last} — run 'qwen-web-arwaky doctor' for diagnostics"
        return "CHECKING — run 'qwen-web-arwaky doctor' for diagnostics"

    def _start_login_worker(self, confirmed: bool) -> None:
        """SA-1: start the blocking login worker after user confirmation."""
        if not confirmed:
            return
        self._login_in_flight = True
        self._log_msg("[bold {}]>>> Launching interactive session setup...[/]".format(THEME["accent_fg"]))
        self._login_worker()

    def action_init_action(self) -> None:
        """U8: trigger workspace initialization on a background thread."""
        self._log_msg("[bold {}]>>> Initializing workspace...[/]".format(THEME["accent_fg"]))
        self._init_worker()

    def _session_login_action(self) -> None:
        """Handle session login button click."""
        if not hasattr(self, "_session_manager") or self._session_manager is None:
            self._log_msg("[yellow]Session manager not available.[/]")
            return
        self.push_screen(
            SessionSetupScreen(
                status_text="Session Login",
                on_login=lambda confirmed: self._run_session_login(confirmed),
                on_back=lambda: self._log_msg("[dim]Login cancelled.[/]"),
            )
        )

    def _run_session_login(self, confirmed: bool) -> None:
        """Run the session login process."""
        if not confirmed:
            return
        self._log_msg("[bold {}]>>> Starting session login...[/]".format(THEME["accent_fg"]))
        # This will be handled by the CLI sessions login command via subprocess
        self.notify(
            "Use 'qwen-web-arwaky sessions login --name <name>' to add a session", title="Info", severity="information"
        )
        self._log_msg("[bold {}]>>> Initializing workspace...[/]".format(THEME["accent_fg"]))
        self._init_worker()

    @work(thread=True)
    def _init_worker(self) -> None:
        from modules.shared.src.taxonomy_core_vo import FilePath

        try:
            self._workspace.init_workspace(FilePath(Path(str(Path.cwd()))))
            cwd = Path.cwd()
            self.call_from_thread(
                self._log_msg,
                "[bold {}]INIT:[/] Workspace initialized in {}".format(THEME["ok"], escape(str(cwd))),
            )
            self.call_from_thread(self.notify, f"Workspace initialized in {cwd}", "information", 3)
        except Exception as exc:
            self.call_from_thread(
                self._log_msg,
                "[bold {}]INIT ERROR:[/] {}".format(THEME["err"], escape(str(exc))),
            )

    def action_request_quit(self) -> None:
        """Quit, requiring confirmation when jobs run or a double-Esc when idle."""
        import time

        active = [s for s, w in self._slot_workers.items() if w is not None]
        if not active:
            # A4: double-escape guard — require two Esc presses within 2s.
            now = time.monotonic()
            last = getattr(self, "_last_esc_time", 0.0)
            if now - last > 2.0:
                self._last_esc_time = now
                # A6: use notify for visibility regardless of active tab
                self.notify("Press Escape again within 2s to quit", timeout=3.0)
                self._log_msg("[{}]Press Escape again within 2s to quit.[/]".format(THEME["muted"]))
                return
            self.exit()
            return

        # U2: never quit silently while jobs are running.
        active_ids = ", ".join(str(s) for s in sorted(active))

        def _confirmed(confirmed: bool | None) -> None:
            if confirmed:
                for s in active:
                    self._cancel_slot(s)
                self.exit()

        self.push_screen(
            ConfirmModal(
                "Confirm Quit",
                f"{len(active)} automation job(s) are still running (Slots: {active_ids}).\n"
                "Quitting will cancel them. Browser processes will be stopped.",
                confirm_label="Quit and Cancel Jobs",
            ),
            _confirmed,
        )


__all__ = ["_TuiHandlersMixin"]
