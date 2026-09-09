"""UI utility helpers for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing stateless-ish helpers used by
compose, handlers, and workers — table management, metrics refresh, slot
status update, log messaging, and the log-handler guard.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.content import Content
from textual.css.query import NoMatches
from textual.widgets import DataTable, Label, RichLog, TabbedContent
from textual.widgets._data_table import CellDoesNotExist

from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler

if TYPE_CHECKING:
    pass


class _TuiUtilsMixin:
    """Mixin for UI utility helpers: table, metrics, status badges, logging."""

    # A1: status text+glyph so meaning never relies on color alone (WCAG 1.4.1).
    _STATUS_ICONS: dict[str, str] = {
        "STATUS: READY": "● READY",
        "STATUS: RUNNING": "▶ RUNNING",
        "STATUS: SUCCESS": "✓ SUCCESS",
        "STATUS: FAILED": "✕ FAILED",
        "STATUS: CANCELLED": "■ CANCELLED",
    }

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _NUM_SLOTS: int
    _slot_stats: dict[int, dict[str, Any]]
    _metrics_pending: bool
    _metric_active: Any
    _metric_done: Any
    _log_handler: logging.Handler

    # ── Overview table ───────────────────────────────────────────────────

    def _init_table(self) -> None:
        with contextlib.suppress(NoMatches):
            table = self.query_one("#slots-table", DataTable)  # type: ignore[attr-defined]
            table.add_columns("Slot", "Status", "Prompt File", "Duration")
            for s in range(1, self._NUM_SLOTS + 1):
                table.add_row(f"Slot {s}", "IDLE 💤", "-", "0.0s", key=f"row-slot-{s}")

    def _update_table_row(self, slot_id: int, status: str, filename: str, duration: str) -> None:
        with contextlib.suppress(NoMatches, CellDoesNotExist):
            table = self.query_one("#slots-table", DataTable)  # type: ignore[attr-defined]
            table.update_cell(f"row-slot-{slot_id}", "Status", status)
            table.update_cell(f"row-slot-{slot_id}", "Prompt File", filename)
            table.update_cell(f"row-slot-{slot_id}", "Duration", duration)

    # ── Metrics bar ──────────────────────────────────────────────────────

    def _refresh_metrics(self) -> None:
        if self._metrics_pending:
            return
        self._metrics_pending = True
        self.set_timer(0.25, self._flush_metrics)  # type: ignore[attr-defined]

    def _flush_metrics(self) -> None:
        self._metrics_pending = False
        with contextlib.suppress(NoMatches):
            active = sum(
                1 for s in self._slot_stats.values() if s.get("status") == "RUNNING"
            )
            done = sum(
                1 for s in self._slot_stats.values() if s.get("status") in {"SUCCESS", "FAILED"}
            )
            if self._metric_active is not None:
                self._metric_active.update(f"ACTIVE: {active}")
            if self._metric_done is not None:
                self._metric_done.update(f"DONE: {done}")

    # ── Slot status / tab title ──────────────────────────────────────────

    def _set_slot_tab_title(self, slot_id: int, title: str) -> None:
        with contextlib.suppress(LookupError, NoMatches):
            tabs = self.query_one(TabbedContent)  # type: ignore[attr-defined]
            tab = tabs.get_tab(f"tab-slot-{slot_id}")
            tab.label = Content.from_text(title)

    def _update_slot_status(self, slot_id: int, status_text: str) -> None:
        with contextlib.suppress(NoMatches):
            badge = self.query_one(f"#status-badge-{slot_id}", Label)  # type: ignore[attr-defined]
            badge.update(self._STATUS_ICONS.get(status_text, status_text))

    @staticmethod
    def _truncate_name(name: str, limit: int = 12) -> str:
        """L3: truncate with an ellipsis instead of a hard cut."""
        return name if len(name) <= limit else name[: limit - 1] + "…"

    # ── Logging helpers ──────────────────────────────────────────────────

    def _ensure_log_handler(self) -> None:
        root = logging.getLogger()
        if hasattr(self, "_log_handler") and not any(
            isinstance(h, QwenTuiLogHandler) for h in root.handlers
        ):
            root.addHandler(self._log_handler)

    def _log_msg(self, msg: str | Text, slot_id: int | None = None) -> None:
        # Truncate plain strings to prevent RichLog horizontal overflow.
        if isinstance(msg, str) and len(msg) > 200:
            msg = msg[:197] + "..."
        with contextlib.suppress(NoMatches):
            if slot_id is not None:
                log_view = self.query_one(f"#log-view-{slot_id}", RichLog)  # type: ignore[attr-defined]
                log_view.write(msg)
            else:
                with contextlib.suppress(NoMatches):
                    self.query_one("#log-view-overview", RichLog).write(msg)  # type: ignore[attr-defined]
                with contextlib.suppress(NoMatches):
                    active_slot = self._get_active_slot_id()  # type: ignore[attr-defined]
                    self.query_one(f"#log-view-{active_slot}", RichLog).write(msg)  # type: ignore[attr-defined]


__all__ = ["_TuiUtilsMixin"]
