"""UI utility helpers for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing stateless-ish helpers used by
compose, handlers, and workers — table management, metrics refresh, slot
status update, log messaging, and the log-handler guard.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any, Literal

from rich.text import Text
from textual.content import Content
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label, RichLog, TabbedContent
from textual.widgets._data_table import CellDoesNotExist

from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler

if TYPE_CHECKING:
    pass

# C1/V1: single source of truth for slot status — one value, one formatter.
SlotStatus = Literal["IDLE", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"]

_STATUS_BADGE: dict[str, str] = {
    "IDLE": "● READY",
    "RUNNING": "▶ RUNNING",
    "SUCCESS": "✓ SUCCESS",
    "FAILED": "✕ FAILED",
    "CANCELLED": "■ CANCELLED",
}
_STATUS_TABLE: dict[str, str] = {
    "IDLE": "IDLE 💤",
    "RUNNING": "RUNNING ⏳",
    "SUCCESS": "DONE ✅",
    "FAILED": "FAILED ❌",
    "CANCELLED": "CANCELLED ✕",
}


class _TuiUtilsMixin:
    """Mixin for UI utility helpers: table, metrics, status badges, logging."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _NUM_SLOTS: int
    _slot_stats: dict[int, dict[str, Any]]
    _metrics_pending: bool
    _metric_active: Any
    _metric_done: Any
    _log_handler: logging.Handler
    _log_views: dict[int, RichLog]

    # Stubs for methods/attrs provided by other mixins / App at runtime.
    query_one: Any
    set_timer: Any
    _get_active_slot_id: Any

    # ── Overview table ───────────────────────────────────────────────────

    # T1: columns are addressed by stable KEYS, never by labels. Textual's
    # add_columns("Status") auto-generates a ColumnKey, so update_cell(row,
    # "Status") raises CellDoesNotExist and every write is a silent no-op.
    COL_SLOT = "slot"
    COL_STATUS = "status"
    COL_FILE = "file"
    COL_DURATION = "duration"

    def _init_table(self) -> None:
        with contextlib.suppress(NoMatches):
            table = self.query_one("#slots-table", DataTable)
            table.add_columns(
                ("Slot", self.COL_SLOT),
                ("Status", self.COL_STATUS),
                ("Prompt File", self.COL_FILE),
                ("Duration", self.COL_DURATION),
            )
            for s in range(1, self._NUM_SLOTS + 1):
                table.add_row(f"Slot {s}", self._format_status("IDLE", "table"), "-", "0.0s", key=f"row-slot-{s}")

    def _update_table_row(self, slot_id: int, status: str, filename: str, duration: str) -> None:
        with contextlib.suppress(NoMatches, CellDoesNotExist):
            table = self.query_one("#slots-table", DataTable)
            row_key = f"row-slot-{slot_id}"
            table.update_cell(row_key, self.COL_STATUS, status)
            table.update_cell(row_key, self.COL_FILE, filename)
            table.update_cell(row_key, self.COL_DURATION, duration)

    # ── Metrics bar ──────────────────────────────────────────────────────

    def _refresh_metrics(self) -> None:
        if self._metrics_pending:
            return
        self._metrics_pending = True
        self.set_timer(0.25, self._flush_metrics)

    def _flush_metrics(self) -> None:
        self._metrics_pending = False
        with contextlib.suppress(NoMatches):
            active = sum(1 for s in self._slot_stats.values() if s.get("status") == "RUNNING")
            done = sum(1 for s in self._slot_stats.values() if s.get("status") in {"SUCCESS", "FAILED"})
            if self._metric_active is not None:
                self._metric_active.update(f"ACTIVE: {active}")
            if self._metric_done is not None:
                self._metric_done.update(f"DONE: {done}")

    # ── Slot status / tab title ──────────────────────────────────────────

    def _format_status(self, status: SlotStatus, target: str) -> str:
        """C1/V1: one status value, one formatter — badge/table never diverge."""
        table = _STATUS_BADGE if target == "badge" else _STATUS_TABLE
        return table.get(status, status)

    def _set_slot_tab_title(self, slot_id: int, title: str) -> None:
        with contextlib.suppress(LookupError, NoMatches):
            tabs = self.query_one(TabbedContent)
            tab = tabs.get_tab(f"tab-slot-{slot_id}")
            tab.label = Content.from_text(title)

    def _update_slot_status(self, slot_id: int, status_text: str) -> None:
        with contextlib.suppress(NoMatches):
            badge = self.query_one(f"#status-badge-{slot_id}", Label)
            badge.update(status_text)

    @staticmethod
    def _truncate_name(name: str, limit: int = 12) -> str:
        """L3: truncate with an ellipsis instead of a hard cut."""
        return name if len(name) <= limit else name[: limit - 1] + "…"

    # ── Logging helpers ──────────────────────────────────────────────────

    def _ensure_log_handler(self) -> None:
        root = logging.getLogger()
        if hasattr(self, "_log_handler") and not any(isinstance(h, QwenTuiLogHandler) for h in root.handlers):
            root.addHandler(self._log_handler)

    def _log_msg(self, msg: str | Text, slot_id: int | None = None) -> None:
        # Truncate plain strings to prevent RichLog horizontal overflow.
        if isinstance(msg, str) and len(msg) > 200:
            msg = msg[:197] + "…"
        views = getattr(self, "_log_views", {})
        if slot_id is not None:
            view = views.get(slot_id)
            if view is not None:
                view.write(msg)
            return
        overview = views.get(0)
        if overview is not None:
            overview.write(msg)
        active = views.get(self._get_active_slot_id())
        if active is not None and active is not overview:
            active.write(msg)


__all__ = ["_TuiUtilsMixin"]
