"""Widget event callbacks for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing the Textual ``on_*`` callbacks
that translate widget events into slot, session, and navigation work. The
button press router lives here because it is one flat decision table over
every control on all four screens; keeping it apart from the ``action_*``
methods in :class:`~modules.cli.src.surface_cli_tui_handlers._TuiHandlersMixin`
keeps each file readable and inside the AES surface complexity budget.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.css.query import NoMatches
from textual.widgets import Button, Input, Select

from modules.cli.src.surface_cli_tui_css import THEME


class _TuiEventsMixin:
    """Mixin that owns widget event callbacks (button, select, input)."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _NUM_SLOTS: int
    _template_roles: set[str]

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Any
    query_one: Any
    _account_button_pressed: Any
    _swarm_button_pressed: Any
    _auth_panel_pressed: Any
    _nav_dock_go: Any
    _switch_to_slot: Any
    _apply_override_from_field: Any
    _apply_override: Any
    _reset_override: Any
    _override_rows: Any
    _show_slot_log: Any
    _open_picker: Any
    _toggle_slot_config: Any
    _apply_template_chip: Any
    _run_slot: Any
    _cancel_slot: Any
    _send_composer: Any
    _copy_log_by_id: Any
    _copy_slot_log: Any
    _refresh_sessions_table: Any
    _session_login_action: Any
    _run_session_health_check: Any
    _check_template_roles: Any
    _refresh_template_selects: Any

    # ── Widget event callbacks ───────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch button presses to slot, swarm, picker, and log-copy handlers."""
        button_id = event.button.id or ""
        # Account cards rebuild on every token re-check, so their actions ride
        # on Button.name instead of an id that would collide with the previous
        # render before the prune lands.
        button_name = event.button.name or ""
        if button_name.startswith("account-test-"):
            position = button_name.removeprefix("account-test-")
            if position.isdigit():
                self._account_button_pressed("test", int(position))
            return
        if button_name.startswith("account-disconnect-"):
            position = button_name.removeprefix("account-disconnect-")
            if position.isdigit():
                self._account_button_pressed("disconnect", int(position))
            return
        if button_id.startswith("btn-swarm-") or button_id == "btn-clear-swarm-log":
            self._swarm_button_pressed(button_id)
            return
        if button_id in ("btn-session-add", "btn-auth-connect", "btn-auth-cancel"):
            self._auth_panel_pressed(button_id)
            return
        if button_id in ("nav-overview", "nav-login", "nav-chat", "nav-swarm", "nav-settings"):
            self._nav_dock_go(button_id)
            return
        # Mockup parity: the chat console's slot carousel jumps straight to the
        # selected slot's tab. The id carries both the pane it was pressed in
        # and the slot it points at (chat-slot-<pane>-<target>).
        if button_id.startswith("chat-slot-"):
            _, _, target = button_id.partition("chat-slot-")
            pane_raw, _, slot_raw = target.partition("-")
            if pane_raw.isdigit() and slot_raw.isdigit():
                self._switch_to_slot(int(slot_raw))
            return
        # Settings pane: write or revert one registered environment value.
        for prefix, handler in (
            ("override-apply-", self._apply_override_from_field),
            ("override-reset-", self._reset_override),
        ):
            if button_id.startswith(prefix):
                handler(button_id.removeprefix(prefix))
                return
        # Chat console: Event/System segmented switch over the slot's logs.
        if button_id.startswith("btn-slot-event-"):
            self._show_slot_log(int(button_id.removeprefix("btn-slot-event-")), False)
            return
        if button_id.startswith("btn-slot-system-"):
            self._show_slot_log(int(button_id.removeprefix("btn-slot-system-")), True)
            return
        # Chat console action pills: prompt picker, attachment picker, and the
        # template selector. The job-config card the fields live in stays
        # hidden until a pill asks for it, so each pill reveals it first.
        if button_id.startswith("btn-pill-prompt-"):
            slot_id = int(button_id.removeprefix("btn-pill-prompt-"))
            self._toggle_slot_config(slot_id)
            self._open_picker(f"input-prompt-{slot_id}")
            return
        if button_id.startswith("btn-pill-attach-"):
            slot_id = int(button_id.removeprefix("btn-pill-attach-"))
            self._toggle_slot_config(slot_id)
            self._open_picker(f"input-file-{slot_id}", select_directories=True)
            return
        if button_id.startswith("btn-pill-templates-"):
            slot_id = int(button_id.removeprefix("btn-pill-templates-"))
            self._toggle_slot_config(slot_id)
            return
        # Clipped job-config chips and Browse buttons (revealed by the pills).
        if button_id.startswith("chip-"):
            self._apply_template_chip(button_id)
            return
        for prefix, handler in (
            ("btn-run-", self._run_slot),
            ("btn-cancel-", self._cancel_slot),
            ("btn-retry-", self._run_slot),
        ):
            if button_id.startswith(prefix):
                suffix = button_id.removeprefix(prefix)
                if suffix.isdigit():
                    handler(int(suffix))
                    return
        for field, picker in (("prompt", False), ("file", True), ("output", False)):
            prefix = f"btn-browse-{field}-"
            if button_id.startswith(prefix):
                slot_id = int(button_id.removeprefix(prefix))
                self._open_picker(f"input-{field}-{slot_id}", select_directories=picker)
                return
        if button_id.startswith("btn-refresh-template-"):
            slot_id = int(button_id.removeprefix("btn-refresh-template-"))
            self._check_template_roles()
            self._log_msg(
                "[{}]Template roles refreshed for slot {}.[/]".format(THEME["muted"], slot_id),
                slot_id,
            )
            return
        # Chat console composer: dispatch the typed task as a direct prompt.
        if button_id.startswith("btn-send-"):
            self._send_composer(int(button_id.removeprefix("btn-send-")))
            return
        if button_id == "btn-copy-log":
            self._copy_log_by_id(button_id)
            return
        if button_id.startswith("btn-copy-log-"):
            slot_id = int(button_id.removeprefix("btn-copy-log-"))
            self._copy_slot_log(slot_id)
            return
        if button_id in ("btn-sessions-refresh", "btn-sessions-rerefresh"):
            self._refresh_sessions_table()
            return
        if button_id == "btn-sessions-login":
            self._session_login_action()
            return
        if button_id == "btn-sessions-health":
            self._run_session_health_check()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Fill the slot's composer from the chosen role template."""
        select_id = event.select.id or ""
        if not select_id.startswith("select-template-"):
            return
        slot_id = int(select_id.split("-")[-1])
        role = event.value
        if not role:
            return
        # P7: lazy-reload template roles so newly added templates are visible
        # without a restart.
        self._check_template_roles()
        with contextlib.suppress(NoMatches):
            composer = self.query_one(f"#composer-{slot_id}", Input)
            composer.value = str(role)
            self._log_msg(
                "[bold {}]TEMPLATE:[/] Slot {} ← role '{}'".format(THEME["bright"], slot_id, escape(str(role))),
                slot_id,
            )
            # U8: optimistic existence hint when the picked value is a file path.
            if str(role) not in self._template_roles and not Path(str(role)).exists():
                self._log_msg(
                    "[{}]WARNING:[/] '{}' is not a known role and the file does not exist.".format(
                        THEME["warn"], escape(str(role))
                    ),
                    slot_id,
                )

    def on_input_changed(self, event: Input.Changed) -> None:
        """U6: keep the template Select in sync with manual path/role entry."""
        input_id = event.input.id or ""
        if not input_id.startswith("input-prompt-"):
            return
        slot_id = int(input_id.split("-")[-1])
        value = event.value.strip()
        with contextlib.suppress(NoMatches):
            select = self.query_one(f"#select-template-{slot_id}", Select)
            if value in self._template_roles:
                select.value = value
            elif select.value not in (None, Select.BLANK) and select.value != value:
                select.value = Select.BLANK

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter inside a composer input sends that slot's typed task."""
        input_id = event.input.id or ""
        if input_id.startswith("composer-"):
            slot_raw = input_id.removeprefix("composer-")
            if slot_raw.isdigit():
                self._send_composer(int(slot_raw))
            return
        # Enter inside an override field applies that value, which is the same
        # gesture as pressing Apply and saves an operator the trip.
        if input_id.startswith("override-input-"):
            suffix = input_id.removeprefix("override-input-")
            for name, _purpose, _default, _secret in self._override_rows():
                if name.replace("-", "_") == suffix:
                    self._apply_override(name, event.value)
                    return


__all__ = ["_TuiEventsMixin"]
