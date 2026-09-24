"""Compose and lifecycle methods for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing the ``compose`` UI tree and
lifecycle hooks (``on_mount``, ``on_unmount``, ``_deferred_startup``).
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler, QwenTuiRichLog
from modules.cli.src.surface_cli_tui_css import THEME
from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT

# NUM_SLOTS is defined in surface_cli_tui_app and passed via the class; we
# import it at runtime to avoid a circular reference.  The mixin uses
# self.NUM_SLOTS_COUNT which QwenTuiApp sets as a class-level attribute.


class _TuiComposeMixin:
    """Mixin that owns the Textual compose tree and app lifecycle hooks."""

    # QwenTuiApp sets this at class level; the mixin reads it.
    _NUM_SLOTS: int
    _template_options: list[tuple[str, str]]
    _slot_workers: dict[int, Any]
    # Declared here to match _TuiUtilsMixin and avoid incompatible-definition error.
    _log_handler: logging.Handler

    # Stubs for methods provided by other mixins / App at runtime.
    _init_table: Any
    _init_swarm_table: Any
    query_one: Any
    set_timer: Any
    _log_msg: Any
    _refresh_session_badge: Any
    _format_status: Any

    # ── Lifecycle ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Build the tabbed layout: overview, swarm, and one pane per slot."""
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            # ─── Tab 1: Overview ────────────────────────────────
            with TabPane("Overview 📊", id="tab-overview"), Vertical(classes="overview-container"):
                with Horizontal(classes="metrics-bar"):
                    yield Label(f"SLOTS: {self._NUM_SLOTS}", id="metric-slots", classes="metric-item")
                    yield Label("ACTIVE: 0", id="metric-active", classes="metric-item")
                    yield Label("DONE: 0", id="metric-done", classes="metric-item")
                    yield Label("SESSION: CHECKING…", id="session-badge", classes="metric-item")

                yield Label("Active Job Slots (1 Browser per Job)", classes="field-label")
                yield DataTable(id="slots-table")

                with Horizontal(classes="pane-title"):
                    yield Label("System Event Log", classes="field-label")
                    yield Button("📋 Copy", id="btn-copy-log", classes="btn-copy-log", variant="default")
                yield QwenTuiRichLog(
                    id="log-view-overview",
                    highlight=True,
                    markup=True,
                    max_lines=2000,
                    auto_scroll=True,
                    wrap=True,
                )
                # A3: help discoverability hint for first-time users
                yield Static(
                    "[dim]Press ? for keyboard shortcuts. Configure a slot tab, then press Enter to run.[/dim]",
                    classes="metric-item",
                )

            # ─── Tab 2: Session Pool ────────────────────────
            with TabPane("Sessions 👤", id="tab-sessions"), Vertical(classes="overview-container"):
                with Horizontal(classes="metrics-bar"):
                    yield Label("SESSION POOL STATUS", classes="metric-item")
                    yield Label("TOTAL: 0", id="session-total", classes="metric-item")
                    yield Label("HEALTHY: 0", id="session-healthy", classes="metric-item")
                    yield Label("LIMITED: 0", id="session-limited", classes="metric-item")
                yield Label("Registered Sessions", classes="field-label")
                yield DataTable(id="sessions-table")
                with Horizontal(classes="toggle-row"):
                    yield Button("🔄 Refresh", id="btn-sessions-refresh", variant="default")
                    yield Button("🔐 Add Session", id="btn-sessions-login", variant="primary")
                    yield Button("🏥 Health Check", id="btn-sessions-health", variant="default")
                yield QwenTuiRichLog(
                    id="log-view-sessions",
                    highlight=True,
                    markup=True,
                    max_lines=500,
                    auto_scroll=True,
                    wrap=True,
                )

            # ─── Tab 3: Adaptive Swarm ─────────────────────────
            with TabPane("Swarm ◈", id="tab-swarm"), Vertical(classes="overview-container"):
                yield Label("Attachment File or Folder", classes="field-label")
                with Horizontal(classes="field-row"):
                    yield Input(
                        value="",
                        placeholder="path/to/file or folder",
                        id="input-swarm-file",
                        classes="field-input",
                    )
                    yield Button("Browse", id="btn-browse-swarm-file", classes="btn-browse")
                with Horizontal(classes="toggle-row"):
                    swarm_env = os.environ.get("QWEN_SWARM_CONCURRENCY", "").strip()
                    swarm_max = min(10, max(1, int(swarm_env))) if swarm_env.isdigit() and int(swarm_env) > 0 else 10
                    yield Button("⚡ START SWARM", variant="primary", id="btn-swarm-start")
                    yield Button("✕ CANCEL SWARM", id="btn-swarm-cancel")
                    yield Label(f"Adaptive templates · maximum {swarm_max} browsers", id="swarm-summary")
                yield DataTable(id="swarm-table")
                with Horizontal(classes="pane-title"):
                    yield Label("Swarm Log", classes="field-label")
                    yield Button("📋 Copy", id="btn-copy-swarm-log", classes="btn-copy-log", variant="default")
                yield QwenTuiRichLog(
                    id="log-view-swarm",
                    highlight=True,
                    markup=True,
                    max_lines=2000,
                    auto_scroll=True,
                    wrap=True,
                )

            # ─── Tabs 2..N: Job Slots ───────────────────────────
            for s in range(1, self._NUM_SLOTS + 1):
                with TabPane(f"Slot {s} ●", id=f"tab-slot-{s}"), Horizontal(classes="slot-container"):
                    with ScrollableContainer(classes="left-pane"):
                        yield Static(f"[ CONFIGURATION: SLOT {s} ]", classes="pane-title")

                        yield Label("Prompt Template (Quick Select)", classes="field-label")
                        yield Select(
                            self._template_options,
                            prompt="Select a template or type file path below",
                            allow_blank=True,
                            id=f"select-template-{s}",
                        )

                        yield Label("Prompt File / Role (Required) *", classes="field-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value="",
                                placeholder="path/to/prompt.md or role (any .md in modules/templates/)",
                                id=f"input-prompt-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-prompt-{s}", classes="btn-browse")

                        yield Label("Attachment File or Folder (Optional)", classes="field-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value="",
                                placeholder="path/to/file or folder",
                                id=f"input-file-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-file-{s}", classes="btn-browse")

                        yield Label("Output Destination", classes="field-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value=str(DEFAULT_OUTPUT),
                                placeholder="path/to/output.md",
                                id=f"input-output-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-output-{s}", classes="btn-browse")

                        with Horizontal(classes="toggle-row"):
                            with Vertical(classes="toggle-label-box"):
                                yield Label("Headless Browser", classes="field-label")
                                yield Label("1 independent browser in background", classes="toggle-subtext")
                            yield Switch(value=True, id=f"switch-headless-{s}")

                        yield Button(
                            f"⚡ RUN IN SLOT {s}", variant="primary", id=f"btn-run-{s}", classes="btn-slot-run"
                        )
                        yield Button(f"✕ Cancel Slot {s}", id=f"btn-cancel-{s}", classes="btn-slot-cancel")
                        yield Button(f"↻ Retry Slot {s}", id=f"btn-retry-{s}", classes="btn-slot-retry")

                    with Vertical(classes="right-pane"):
                        with Horizontal(classes="pane-title"):
                            yield Label(f"[ LIVE LOG: BROWSER #{s} ]", classes="field-label")
                            yield Label(
                                self._format_status("IDLE", "badge"), id=f"status-badge-{s}", classes="status-badge"
                            )
                            yield Button("📋", id=f"btn-copy-log-{s}", classes="btn-copy-log", tooltip="Copy slot log")
                        yield LoadingIndicator(id=f"loading-{s}", classes="slot-loading")
                        yield QwenTuiRichLog(
                            id=f"log-view-{s}",
                            highlight=True,
                            markup=True,
                            classes="slot-log-view",
                            max_lines=2000,
                            wrap=True,
                        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialise tables, cache widget refs, and defer log startup."""
        self._init_table()
        self._init_swarm_table()

        # P3: cache metric widget refs once; no per-call DOM lookups.
        self._metric_active = self.query_one("#metric-active", Label)
        self._metric_done = self.query_one("#metric-done", Label)

        # P1: cache RichLog widget refs at mount time — hot render path.
        self._log_views: dict[int, QwenTuiRichLog] = {}
        with contextlib.suppress(NoMatches):
            self._log_views[0] = self.query_one("#log-view-overview", QwenTuiRichLog)
        with contextlib.suppress(NoMatches):
            self._log_views[-1] = self.query_one("#log-view-swarm", QwenTuiRichLog)
        for s in range(1, self._NUM_SLOTS + 1):
            with contextlib.suppress(NoMatches):
                self._log_views[s] = self.query_one(f"#log-view-{s}", QwenTuiRichLog)

        # P5: defer RichLog writes until after first paint to avoid overlay glitch.
        self.set_timer(0.4, self._deferred_startup)

    def _deferred_startup(self) -> None:
        """Attach log handler and write initial messages after first paint."""
        root = logging.getLogger()

        # Keep existing stderr/file handlers attached. The TUI handler is an
        # additional view and must not disable operational logging on unmount.
        for handler in list(root.handlers):
            if isinstance(handler, QwenTuiLogHandler):
                root.removeHandler(handler)

        self._log_handler = QwenTuiLogHandler(self)
        self._log_handler.setLevel(logging.INFO)
        root.addHandler(self._log_handler)

        self._log_msg(
            f"[bold {THEME['accent_fg']}]Qwen Web Automation TUI initialized with multi-slot architecture.[/]"
        )
        self._log_msg(f"[{THEME['muted']}]Each slot runs an independent Chromium process sharing login state.[/]")

        # U5: seed per-slot log views with an empty-state hint.
        for s in range(1, self._NUM_SLOTS + 1):
            with contextlib.suppress(NoMatches):
                log_view = self.query_one(f"#log-view-{s}", QwenTuiRichLog)
                log_view.auto_scroll = True
                log_view.write(f"[{THEME['muted']}]Set a prompt file, then press Enter or RUN.[/]")

        self._refresh_session_badge()

    def on_unmount(self) -> None:
        """Detach the TUI log handler and cancel running slot workers."""
        if hasattr(self, "_log_handler"):
            logging.getLogger().removeHandler(self._log_handler)
        # U2: best-effort cancellation of running slot workers on exit.
        for worker in list(self._slot_workers.values()):
            if worker is not None:
                with contextlib.suppress(Exception):
                    worker.cancel()


__all__ = ["_TuiComposeMixin"]
