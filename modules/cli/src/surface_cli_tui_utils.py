"""UI utility helpers for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing stateless-ish helpers used by
compose, handlers, and workers — table management, metrics refresh, slot
status update, log messaging, and the log-handler guard.
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from rich.markup import escape
from rich.text import Text
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.content import Content
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Label, Static, TabbedContent
from textual.widgets._data_table import CellDoesNotExist

from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler, QwenTuiRichLog
from modules.shared.src.taxonomy_swarm_vo import SwarmRequest

if TYPE_CHECKING:
    pass

# C1/V1: single source of truth for slot status — one value, one formatter.
SlotStatus = Literal["IDLE", "RUNNING", "SUCCESS", "FAILED", "CANCELLED", "CANCELLING"]

_STATUS_BADGE: dict[str, str] = {
    "IDLE": "● READY",
    "RUNNING": "▶ RUNNING",
    "SUCCESS": "✓ SUCCESS",
    "FAILED": "✕ FAILED",
    "CANCELLED": "■ CANCELLED",
    "CANCELLING": "⚠ CANCELLING…",
}
_STATUS_TABLE: dict[str, str] = {
    "IDLE": "IDLE ●",
    "RUNNING": "RUNNING ▶",
    "SUCCESS": "DONE ✓",
    "FAILED": "FAILED ✕",
    "CANCELLED": "CANCELLED ■",
    "CANCELLING": "CANCELLING ⚠",
}

# Event-level status: monospace glyphs + short label per pipeline event so the
# slot badge/table can show the actual phase (thinking / streaming / prompting)
# instead of only RUNNING. The key is the canonical QwenEventType name with
# the leading "EVENT_" stripped.
_EVENT_BADGE: dict[str, str] = {
    "NETWORK_RECONNECTING": "⚠ RECONNECTING",
    "WEB_LOADED": "◌ LOADING",
    "FILE_UPLOADED": "⇪ UPLOADING",
    "PROMPT_INJECTED": "✎ PROMPTING",
    "DOCUMENT_PARSED": "⊞ PARSING",
    "SEND_CLICKED": "→ SENDING",
    "DISPATCH_ACKNOWLEDGED": "✓ SENT",
    "THINKING_STARTED": "◔ THINKING",
    "STREAMING_GENERATION": "≡ STREAMING",
    "GENERATION_FINISHED": "✓ FINISHED",
    "OUTPUT_COPIED": "✓ SAVED",
    "LOGIN_VERIFIED": "✓ LOGGED IN",
    "MODEL_VERIFIED": "✓ MODEL",
    "FAILED": "✕ FAILED",
}


def format_event_label(event_name: str) -> str:
    """Return a monospace badge for a lifecycle event name.

    Accepts either the full ``QwenEventType`` name (e.g. ``EVENT_THINKING_STARTED``)
    or the stripped form (``THINKING_STARTED``). Falls back to RUNNING when the
    event is unknown.
    """
    key = event_name.removeprefix("EVENT_")
    if key in _EVENT_BADGE:
        return _EVENT_BADGE[key]
    return _STATUS_BADGE["RUNNING"]


# Redesign v6.5.2: thread-state labels used by the Overview Threads Matrix.
# The mockup names each cell's state in one short word (Streaming / Ready /
# Done / Active / Idle) rather than the pipeline event name, so the table
# stays scannable at a glance.
_THREAD_STATE: dict[str, tuple[str, str]] = {
    "IDLE": ("Idle", "grey61"),
    "RUNNING": ("Active", "cyan"),
    "SUCCESS": ("Done", "green"),
    "FAILED": ("Failed", "red"),
    "CANCELLED": ("Cancelled", "grey61"),
    "CANCELLING": ("Stopping", "yellow"),
}


def _thread_state(status: str) -> tuple[str, str]:
    """Return the (label, rich-style) pair an engine readout shows for *status*."""
    return _THREAD_STATE.get(status, _THREAD_STATE["IDLE"])


def _format_thread_duration(seconds: float) -> str:
    """Format a thread duration the way the mockup does (4m12s, 0.0s, 1h 2m)."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60):02d}m"


def _cluster_bar_markup(n_slots: int, stats: dict[int, dict[str, Any]]) -> str:
    """Render the Overview cluster segment bar as Rich markup.

    The mockups draw a 10-cell bar under the Swarm and Chat cards, each cell
    tinted by that slot's state. A terminal cannot tint individual cells from a
    single Label, so each cell is emitted as its own block glyph wrapped in the
    status colour. The compose tree is built before any slot state exists, so
    ``stats`` may be empty, which renders every cell as idle.
    """
    parts: list[str] = []
    for slot in range(1, n_slots + 1):
        status = str(stats.get(slot, {}).get("status", "IDLE"))
        parts.append(f"[{_THREAD_STATE.get(status, _THREAD_STATE['IDLE'])[1]}]█[/]")
    return "".join(parts)


def _empty_cluster_bar_markup(n_slots: int) -> str:
    """Render the all-idle cluster bar used as the compose-time placeholder."""
    return _cluster_bar_markup(n_slots, {})


# Transcript budget: one entry is capped so a single huge model answer cannot
# blow up a Static, and the pane keeps only its newest messages so the
# fixed-height chat console never accumulates unbounded widgets.
_MAX_TRANSCRIPT_CHARS = 4000
_MAX_TRANSCRIPT_MESSAGES = 40


def _attachment_chip(path_str: str) -> str:
    """Format an attachment the way the mockup's chip does (name, size, tick)."""
    path = Path(path_str)
    label = path.name or path_str
    try:
        if path.is_file():
            label = f"{label} ({path.stat().st_size // 1024}KB)"
    except OSError:
        pass
    return f"📄 {label} ✓ ATTACHED"


class _TuiUtilsMixin:
    """Mixin for UI utility helpers: table, metrics, status badges, logging."""

    # Class-level annotations for attributes set by QwenTuiApp.__init__.
    _NUM_SLOTS: int
    _slot_stats: dict[int, dict[str, Any]]
    _metrics_pending: bool
    _metric_active: Any
    _metric_done: Any
    _metric_model: Any
    _metric_swarm_ring: Any
    _metric_swarm_detail: Any
    _metric_swarm_uptime: Any
    _metric_threads_ring: Any
    _metric_threads_detail: Any
    _metric_swarm_bar: Any
    _metric_threads_bar: Any
    _log_handler: logging.Handler
    _log_views: dict[int, QwenTuiRichLog]
    _system_log_views: dict[int, QwenTuiRichLog]
    _chat_scrolls: dict[int, ScrollableContainer]
    _chat_hints: dict[int, Static]
    _slot_log_times: dict[int, Label]
    _swarm_id: str | None
    _swarm: Any
    _swarm_started_perf: float | None

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

    # THREADS MATRIX columns. The mockup's grid shows a zero-padded index, the
    # thread's one-word state, and its elapsed time, so those are the three
    # cells each matrix row carries.
    COL_MTX_INDEX = "mtx-index"
    COL_MTX_STATE = "mtx-state"
    COL_MTX_DURATION = "mtx-duration"

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

    def _init_threads_matrix(self) -> None:
        """Seed the Overview THREADS MATRIX with one idle cell per job slot.

        The mockup draws the matrix as the Overview's main content: a
        two-column grid of numbered cells, each showing the thread's state
        and elapsed time. Rows are keyed by slot id so _update_threads_matrix
        writes cells in place instead of rebuilding the table, which would
        drop the user's scroll position on every metrics tick.
        """
        with contextlib.suppress(NoMatches):
            table = self.query_one("#threads-matrix", DataTable)
            table.add_columns(
                ("#", self.COL_MTX_INDEX),
                ("Thread", self.COL_MTX_STATE),
                ("Elapsed", self.COL_MTX_DURATION),
            )
            for s in range(1, self._NUM_SLOTS + 1):
                table.add_row(
                    f"{s:02d}",
                    _thread_state("IDLE")[0],
                    "0.0s",
                    key=f"mtx-slot-{s}",
                )

    def _update_threads_matrix(self, slot_id: int, status: str, duration: str) -> None:
        """Write one THREADS MATRIX cell pair (state label, elapsed time).

        The state label is colourised by wrapping it in the Rich style the
        mockup pairs with that state (cyan for running, green for done, grey
        for idle), so a glance at the matrix reads the same way the mockup's
        cells do.
        """
        with contextlib.suppress(NoMatches, CellDoesNotExist):
            table = self.query_one("#threads-matrix", DataTable)
            state_label, state_color = _thread_state(status)
            table.update_cell(
                f"mtx-slot-{slot_id}",
                self.COL_MTX_STATE,
                Text(f"{state_label}", style=state_color),
            )
            table.update_cell(f"mtx-slot-{slot_id}", self.COL_MTX_DURATION, duration)

    def _update_table_row(self, slot_id: int, status: str, filename: str, duration: str) -> None:
        with contextlib.suppress(NoMatches, CellDoesNotExist):
            table = self.query_one("#slots-table", DataTable)
            row_key = f"row-slot-{slot_id}"
            table.update_cell(row_key, self.COL_STATUS, status)
            table.update_cell(row_key, self.COL_FILE, filename)
            table.update_cell(row_key, self.COL_DURATION, duration)

    def _init_swarm_table(self) -> None:
        with contextlib.suppress(NoMatches):
            table = self.query_one("#swarm-table", DataTable)
            table.add_columns(
                ("Agent", "swarm-agent"),
                ("Status", "swarm-status"),
                ("Attempt", "swarm-attempt"),
                ("Output", "swarm-output"),
            )
            table.add_row(
                "—",
                "IDLE",
                "—",
                "No active swarm — select an attachment above and click START SWARM",
                key="swarm-empty",
            )

    def _render_swarm_snapshot(self, snapshot: Any) -> None:
        with contextlib.suppress(NoMatches):
            table = self.query_one("#swarm-table", DataTable)
            table.clear()
            for agent in snapshot.agents:
                output = str(agent.output_path) if agent.status == "completed" and agent.output_path else "-"
                table.add_row(
                    agent.agent_id,
                    agent.status.upper(),
                    f"{agent.attempt}/{snapshot.max_attempts}",
                    output,
                    key=f"swarm-{agent.agent_id}",
                )
            summary = self.query_one("#swarm-summary", Label)
            summary.update(
                f"{snapshot.status.upper()} · {snapshot.completed_count}/{len(snapshot.agents)} completed · "
                f"{snapshot.failed_count} failed · max {snapshot.browser_concurrency} browsers"
            )

    # ── Metrics bar ──────────────────────────────────────────────────────

    def _refresh_metrics(self) -> None:
        if self._metrics_pending:
            return
        self._metrics_pending = True
        self.set_timer(0.25, self._flush_metrics)

    def _flush_metrics(self) -> None:
        self._metrics_pending = False
        stats = getattr(self, "_slot_stats", {})
        n_slots = getattr(self, "_NUM_SLOTS", 0)
        active = sum(1 for s in stats.values() if s.get("status") == "RUNNING")
        done = sum(1 for s in stats.values() if s.get("status") in {"SUCCESS", "FAILED"})
        idle = sum(1 for s in stats.values() if s.get("status") == "IDLE")

        with contextlib.suppress(NoMatches):
            if self._metric_active is not None:
                self._metric_active.update(f"{active}")
            if self._metric_done is not None:
                self._metric_done.update(f"{done}")
        with contextlib.suppress(NoMatches):
            swarm_ring = getattr(self, "_metric_swarm_ring", None)
            if swarm_ring is not None:
                swarm_active, swarm_total, _ = self._swarm_engine_state()
                swarm_ring.update(f"{swarm_active}/{swarm_total}")
        with contextlib.suppress(NoMatches):
            threads_ring = getattr(self, "_metric_threads_ring", None)
            if threads_ring is not None:
                threads_ring.update(f"{active}/{n_slots}")
        with contextlib.suppress(NoMatches):
            swarm_detail = getattr(self, "_metric_swarm_detail", None)
            if swarm_detail is not None:
                swarm_active, _swarm_total, _uptime = self._swarm_engine_state()
                swarm_detail.update(f"{swarm_active} Running" if swarm_active else "Idle")
        with contextlib.suppress(NoMatches):
            swarm_uptime = getattr(self, "_metric_swarm_uptime", None)
            if swarm_uptime is not None:
                _swarm_active, _swarm_total, uptime = self._swarm_engine_state()
                swarm_uptime.update(
                    f"Uptime Elapsed {_format_thread_duration(uptime)}" if uptime > 0 else "Uptime Elapsed —"
                )
        with contextlib.suppress(NoMatches):
            threads_detail = getattr(self, "_metric_threads_detail", None)
            if threads_detail is not None:
                threads_detail.update(f"{active} Running · {idle} Idle")
        with contextlib.suppress(NoMatches):
            swarm_bar = getattr(self, "_metric_swarm_bar", None)
            if swarm_bar is not None:
                swarm_bar.update(_cluster_bar_markup(n_slots, stats))
        with contextlib.suppress(NoMatches):
            threads_bar = getattr(self, "_metric_threads_bar", None)
            if threads_bar is not None:
                threads_bar.update(_cluster_bar_markup(n_slots, stats))
        # Per-slot state for the THREADS MATRIX — one cell per job slot.
        with contextlib.suppress(NoMatches):
            for s in range(1, n_slots + 1):
                slot = stats.get(s, {"status": "IDLE", "duration": 0.0})
                status = str(slot.get("status", "IDLE"))
                duration = float(slot.get("duration", 0.0))
                self._update_threads_matrix(s, status, _format_thread_duration(duration))

    # ── Swarm engine readout ─────────────────────────────────────────────

    def _swarm_engine_state(self) -> tuple[int, int, float]:
        """Return (active_agents, total_agents, uptime_seconds) for the Swarm card.

        The Overview's Swarm Status card tracks the adaptive swarm, which is a
        different resource from the per-slot job threads tracked by the Chat
        Status card. Before a swarm starts there are no agents, so the card
        reads 0/0 and Idle rather than borrowing the slot counters.
        """
        snapshot_id = getattr(self, "_swarm_id", None)
        if snapshot_id is None:
            return 0, 0, 0.0
        swarm = getattr(self, "_swarm", None)
        if swarm is None:
            return 0, 0, 0.0
        try:
            snapshot = swarm.execute(SwarmRequest(verb="snapshot", swarm_id=snapshot_id)).snapshot
        except Exception:
            return 0, 0, 0.0
        if snapshot is None:
            return 0, 0, 0.0
        agents = list(snapshot.agents)
        running = sum(1 for a in agents if str(a.status) == "running")
        started = getattr(self, "_swarm_started_perf", None)
        uptime = (time.perf_counter() - started) if started else 0.0
        return running, len(agents), uptime

    # ── Slot status / tab title ──────────────────────────────────────────

    def _format_status(self, status: SlotStatus, target: str) -> str:
        """C1/V1: one status value, one formatter — badge/table never diverge.

        For RUNNING slots an optional event-level status can be shown via the
        ``event_status`` parameter, which renders the current pipeline event
        (thinking / streaming / prompting) instead of a generic RUNNING label.
        """
        table = _STATUS_BADGE if target == "badge" else _STATUS_TABLE
        return table.get(status, status)

    def _format_event_status(self, status: str | None, target: str) -> str:
        """Render an event-level status for a RUNNING slot.

        ``status`` is either a canonical ``QwenEventType`` name (with or
        without the ``EVENT_`` prefix) or one of the base slot statuses.
        A ``None`` value falls back to a plain RUNNING label. The result is
        a monospace glyph + label suitable for a badge or a table cell.
        """
        if status is None:
            return self._format_status("RUNNING", target)
        if status in _STATUS_BADGE:
            base: SlotStatus = cast(SlotStatus, status)
            return self._format_status(base, target)
        label = format_event_label(status)
        if target == "badge":
            return label
        # Table cells keep the leading RUNNING marker for scanability.
        return f"{_STATUS_TABLE['RUNNING']} · {label}"

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
            self._stamp_slot_log(slot_id)
            return
        overview = views.get(0)
        if overview is not None:
            overview.write(msg)
        # Mockup parity: a chat console carries two buffers. Slot-scoped
        # writes above feed the EVENT LOG; unscoped application records feed
        # the SYSTEM LOG of whichever slot is on screen.
        active = self._get_active_slot_id()
        system = getattr(self, "_system_log_views", {}).get(active)
        if system is not None:
            system.write(msg)
        self._stamp_slot_log(active)

    def _stamp_slot_log(self, slot_id: int) -> None:
        """Advance the chat console's trailing log clock (mockup's 09:46:31)."""
        label = getattr(self, "_slot_log_times", {}).get(slot_id)
        if label is not None:
            label.update(time.strftime("%H:%M:%S"))

    def _append_chat_message(
        self,
        slot_id: int,
        role: str,
        text: str,
        attachment: str = "",
    ) -> None:
        """Render one transcript entry in a slot's chat console.

        ``role`` is ``user`` (right-aligned operator prompt) or ``agent``
        (left-aligned Qwen answer). The empty-state hint sits in the
        transcript until the first message replaces it, and the transcript
        keeps only its newest entries so a long session cannot grow without
        bound in a fixed-height pane.
        """
        # The caches are populated in ``on_mount``; a worker can outlive the
        # mount (or a test can drive the mixin without one), so a missing
        # cache means there is no transcript to write to — not an error.
        scroll = getattr(self, "_chat_scrolls", {}).get(slot_id)
        if scroll is None:
            return
        hint = getattr(self, "_chat_hints", {}).pop(slot_id, None)
        if hint is not None and hint.is_attached:
            with contextlib.suppress(Exception):
                hint.remove()
        stamp = time.strftime("%H:%M:%S")
        if len(text) > _MAX_TRANSCRIPT_CHARS:
            text = text[: _MAX_TRANSCRIPT_CHARS - 1] + "…"
        body = escape(text)
        if role == "user":
            blocks: list[Static] = [
                Static("DEV OPERATOR", classes="msg-author msg-author-right"),
                Static(body, classes="msg-bubble msg-bubble-user"),
            ]
            if attachment:
                blocks.append(Static(_attachment_chip(attachment), classes="msg-attach"))
            blocks.append(Static(stamp, classes="msg-time msg-time-user"))
            message = Vertical(*blocks, classes="msg msg-user")
        else:
            message = Vertical(
                Static("QWEN3.8-MAX", classes="msg-author"),
                Static(body, classes="msg-bubble"),
                Static(stamp, classes="msg-time"),
                classes="msg msg-agent",
            )
        with contextlib.suppress(Exception):
            scroll.mount(message)
            # Removal is deferred by one message pump, so stop as soon as the
            # head of the list stops changing instead of looping on a stale
            # children tuple.
            while len(scroll.children) > _MAX_TRANSCRIPT_MESSAGES:
                head = scroll.children[0]
                head.remove()
                if head in scroll.children:
                    break
            scroll.scroll_end(animate=False)

    # ── Sessions: mockup account cards ───────────────────────────────────

    @staticmethod
    def _account_card(session: Any, position: int) -> Vertical:
        """Build one mockup account card from a stored session record.

        The card mirrors the Login mockup: identity on top, then a hairline
        row carrying the health state and the two per-account actions. The
        actions ride on ``Button.name`` rather than ``id`` so a re-check can
        rebuild the whole list without ever registering a duplicate id.
        """
        name = str(getattr(session, "name", "") or getattr(session, "session_id", "") or f"session-{position}")
        healthy = bool(getattr(session, "is_healthy", False))
        status = getattr(getattr(session, "status", None), "value", "") or ""
        if healthy:
            label, state_class = "ACTIVE", "state-active"
        else:
            label, state_class = str(status).upper() or "LIMITED", "state-limited"
        return Vertical(
            Horizontal(
                Static(name[:1].upper() or "◍", classes="account-avatar"),
                Static(escape(name), classes="account-email"),
                classes="account-card-head",
            ),
            Horizontal(
                Static(f"● {label}", classes=f"account-status {state_class}"),
                Button("TEST", name=f"account-test-{position}", classes="account-btn account-btn-test"),
                Button("EXIT", name=f"account-disconnect-{position}", classes="account-btn account-btn-disconnect"),
                classes="account-card-foot",
            ),
            classes="account-card",
        )

    def _render_account_cards(self, sessions: list[Any]) -> None:
        """Replace the Sessions pane's card list with one card per session.

        The list is rebuilt rather than diffed: a token re-check rewrites the
        health state of every account at once, so incremental updates would
        have to reconcile states that all change together anyway.
        """
        with contextlib.suppress(NoMatches):
            container = self.query_one("#account-cards", Vertical)
            container.remove_children()
            if not sessions:
                container.mount(Static("No accounts registered.", classes="field-label"))
                return
            # The card actions are addressed by position, so the handler
            # resolves them against exactly the list on screen.
            self._sessions_cache = list(sessions)
            for position, session in enumerate(sessions, start=1):
                container.mount(self._account_card(session, position))


__all__ = ["_TuiUtilsMixin", "SlotStatus", "format_event_label"]
