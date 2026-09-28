"""Runtime override editing for the Qwen TUI Settings screen.

Surface layer (surface_cli): Mixin backing the Settings screen's RUNTIME
OVERRIDES card. It reads the environment registry the same way ``doctor``
does, lets the operator write a value, and persists that write to the XDG
override file so the choice survives a restart.

Two rules shape this module. First, an empty field means *revert to default*,
never "set to empty" — the defaults are the product, this screen only adjusts
them. Second, the value is written twice: into ``os.environ`` so the next run
or Swarm start in the same session sees it, and into the file so the next
launch does too.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

from rich.markup import escape
from textual.css.query import NoMatches
from textual.widgets import Input, Static

from modules.cli.src.surface_cli_tui_css import THEME
from modules.shared.src.utility_core_env import (
    REGISTERED_ENV,
    clear_settings,
    is_secret,
    load_settings,
    save_settings,
    settings_path,
    validate_env,
)

#: Override records go to the Overview event log (slot 0), not to a slot's
#: event log: a change to a process-wide value belongs to no single slot.
_OVERRIDE_LOG_SLOT = 0

#: Values that need a restart before they take effect, with the reason shown
#: in the row's badge. Everything else is read on the next operation.
_RESTART_REQUIRED: dict[str, str] = {
    "QWEN_WEB_MAX_WORKERS": "executor pool built at start",
    "PLAYWRIGHT_BROWSERS_PATH": "browser path cached at start",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "tracing wired at start",
    "OTEL_SERVICE_NAME": "tracing wired at start",
    "SENTRY_DSN": "error tracking wired at start",
    "ENVIRONMENT": "log handler chosen at start",
}


class _TuiSettingsMixin:
    """Mixin providing the runtime-override rows of the Settings screen."""

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    _log_msg: Any
    query_one: Any
    _NUM_SLOTS: int

    # ── Reading the registry ───────────────────────────────────────────

    def _override_rows(self) -> tuple[tuple[str, str, str, bool], ...]:
        """Return the registry entries the override card renders, in name order.

        Sorts by name so the row order is stable across restarts: an operator
        who learned where a value lives does not have to hunt for it again
        because the registry tuple was reordered.
        """
        return tuple(sorted(REGISTERED_ENV, key=lambda entry: entry[0]))

    def _override_default(self, name: str) -> str:
        """Return the registry default shown when *name* has no override."""
        for entry_name, _purpose, default, _secret in self._override_rows():
            if entry_name == name:
                return default
        return ""

    def _override_active(self, name: str) -> str:
        """Return the override in force for *name*, or the empty string.

        The process environment counts as an override because a shell export
        beats the stored file, and the operator should see the value that is
        actually running rather than the one they last typed.
        """
        return os.environ.get(name, "").strip()

    def _override_display(self, name: str) -> str:
        """Return the value to show in *name*'s field, secrets masked."""
        value = self._override_active(name)
        if not value:
            return self._override_default(name)
        if is_secret(name):
            return "***"
        return value

    def _override_badge(self, name: str) -> tuple[str, str]:
        """Return ``(text, css_class)`` for the state badge beside *name*.

        Three states matter to an operator: the value is in force right now,
        it is stored and waits for a restart, or the default applies.
        """
        reason = _RESTART_REQUIRED.get(name)
        if self._override_active(name):
            if reason:
                return (f"RESTART · {reason}", "override-badge override-badge-restart")
            return ("ACTIVE NOW", "override-badge override-badge-active")
        return (f"DEFAULT · {self._override_default(name) or 'unset'}", "override-badge")

    # ── Writing an override ───────────────────────────────────────────

    def _apply_override_from_field(self, name: str) -> None:
        """Apply whatever *name*'s field currently holds.

        The router's entry point: the field is the source of the value, so a
        press on Apply and Enter in the field take the same path.
        """
        with contextlib.suppress(Exception):
            value = self.query_one(f"#override-input-{name.replace('-', '_')}", Input).value
            self._apply_override(name, value)
            return
        self._apply_override(name, "")

    def _apply_override(self, name: str, raw_value: str) -> None:
        """Persist *raw_value* for *name*, or revert it when the field is empty.

        Rejects a value the registry itself would flag, because storing it
        would mean a restart behaves differently from the session that typed
        it — the exact surprise this screen exists to remove.
        """
        value = raw_value.strip()
        if not value:
            self._reset_override(name)
            return
        if validate_env({name: value}):
            self._log_msg(
                "[{}]REJECTED:[/] '{}' is not a valid value for {}.".format(THEME["warn"], escape(value), escape(name)),
                _OVERRIDE_LOG_SLOT,
            )
            self._refresh_override_row(name)
            return
        self._store_override(name, value)
        self._refresh_override_row(name)
        badge, _css = self._override_badge(name)
        # The log is a record, not a display: a registered secret is named but
        # never echoed, here or anywhere else that copies a value out.
        shown = "***" if is_secret(name) else value
        self._log_msg(
            "[bold {}]OVERRIDE:[/] {} = {} [{}]({})[/]".format(
                THEME["bright"], escape(name), escape(shown), THEME["muted"], escape(badge)
            ),
            _OVERRIDE_LOG_SLOT,
        )

    def _store_override(self, name: str, value: str) -> None:
        """Write *name* into the process environment and the override file."""
        os.environ[name] = value
        stored = dict(self._load_stored())
        stored[name] = value
        save_settings(stored)

    def _load_stored(self) -> dict[str, str]:
        """Return the override file's current contents."""
        return load_settings()

    def _show_settings_section(self, overrides: bool) -> None:
        """Show the runtime-override card or the per-slot form, not both.

        The slot carousel only belongs to the form, so it leaves with it —
        leaving ten pills above a list of environment variables would imply
        they still selected something.
        """
        for target, visible in (
            ("#settings-overrides", overrides),
            (".settings-carousel", not overrides),
        ):
            with contextlib.suppress(NoMatches):
                self.query_one(target).display = visible
        for slot in range(1, self._NUM_SLOTS + 1):
            with contextlib.suppress(NoMatches):
                self.query_one(f"#slot-config-{slot}").display = (not overrides) and slot == 1
        for tab_id, active in (
            ("settings-tab-slot", not overrides),
            ("settings-tab-overrides", overrides),
        ):
            with contextlib.suppress(NoMatches):
                self.query_one(f"#{tab_id}").set_class(active, "seg-active")
        if overrides:
            self._refresh_all_overrides()

    def _reset_override(self, name: str) -> None:
        """Drop the override for *name* so its registry default applies again."""
        if not self._override_active(name):
            self._refresh_override_row(name)
            return
        clear_settings([name])
        self._refresh_override_row(name)
        self._log_msg(
            "[bold {}]RESET:[/] {} back to '{}'.".format(
                THEME["bright"], escape(name), escape(self._override_default(name) or "unset")
            ),
            _OVERRIDE_LOG_SLOT,
        )

    # ── Rendering ─────────────────────────────────────────────────────

    def _refresh_override_row(self, name: str) -> None:
        """Re-render *name*'s field and badge after a write or a reset."""
        suffix = name.replace("-", "_")
        with contextlib.suppress(Exception):
            self.query_one(f"#override-input-{suffix}", Input).value = self._override_display(name)
        with contextlib.suppress(Exception):
            badge = self.query_one(f"#override-badge-{suffix}", Static)
            text, css = self._override_badge(name)
            badge.update(text)
            badge.remove_class("override-badge-active", "override-badge-restart")
            for token in css.split():
                badge.add_class(token)

    def _refresh_all_overrides(self) -> None:
        """Re-render every override row, so the card opens showing real values."""
        for name, _purpose, _default, _secret in self._override_rows():
            self._refresh_override_row(name)

    def _override_hint(self) -> str:
        """Return the footer line naming the file the values are stored in."""
        return f"Stored in {settings_path()} · process environment wins over this file"


__all__ = ["_TuiSettingsMixin"]
