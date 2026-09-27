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
from modules.cli.src.surface_cli_tui_utils import _empty_cluster_bar_markup
from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL, DEFAULT_OUTPUT


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
    _init_threads_matrix: Any
    query_one: Any
    set_timer: Any
    _log_msg: Any
    _refresh_session_badge: Any
    _format_status: Any
    _truncate_name: Any
    _flush_metrics: Any
    _refresh_nav_dock: Any

    # ── Lifecycle ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Build the tabbed layout: overview, swarm, and one pane per slot."""
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            # ─── Tab 1: Overview ────────────────────────────────
            with TabPane("Overview", id="tab-overview"), Vertical(classes="overview-container"):
                # Redesign v6.5.2 (mockup): the Overview is a header strip, a
                # Swarm Status card, a Chat Status card carrying the THREADS
                # MATRIX, and a log strip. The terminal keeps the two engine
                # cards folded into one bordered block and splits the vertical
                # space the way the mockup does — the matrix is the content
                # that scrolls, the log is a band pinned to the bottom:
                #
                #   readouts card   height auto (4 rows, never compressed)
                #   THREADS MATRIX  height 1fr  (scrolls when short on rows)
                #   slot table      height 3    (pinned, scrolls its rows)
                #   log strip       height 4    (pinned, never squeezed to 0)
                #
                # tests/unit_tui_log_containment.py locks the last two so a
                # table can never take the log's rows again (PR #249/#250).
                with Vertical(id="overview-engine-card", classes="engine-card"):
                    # Header strip: the mockup's ACTIVE ACCOUNTS and MODEL
                    # tiles, flattened onto one row so the cards below keep
                    # their geometry on short terminals.
                    with Horizontal(classes="engine-header-strip"):
                        yield Label("● ACTIVE", id="metric-active-label", classes="section-label")
                        yield Label("0", id="metric-active", classes="metric-accent")
                        yield Label("│", classes="metric-divider")
                        yield Label("MODEL", id="metric-model-label", classes="section-label")
                        yield Label(DEFAULT_MODEL, id="metric-model", classes="metric-accent")
                        yield Label("│", classes="metric-divider")
                        yield Label("SLOTS", id="metric-slots-label", classes="section-label")
                        yield Label(f"{self._NUM_SLOTS}", id="metric-slots", classes="metric-value")
                        yield Label("│", classes="metric-divider")
                        yield Label("DONE", id="metric-done-label", classes="section-label")
                        yield Label("0", id="metric-done", classes="metric-value")
                        yield Label("│", classes="metric-divider")
                        yield Label("SESSION", id="metric-session-label", classes="section-label")
                        yield Label("CHECKING…", id="session-badge", classes="metric-value")

                    # Swarm Status card: ring, name, and the uptime readout the
                    # mockup pins to the card's right edge.
                    with Horizontal(classes="engine-readout"):
                        yield Label("0/0", id="metric-swarm-ring", classes="engine-ring")
                        yield Label("SWARM", id="metric-swarm-label", classes="engine-name")
                        yield Label("Idle", id="metric-swarm-detail", classes="engine-detail")
                        yield Label("Uptime —", id="metric-swarm-uptime", classes="engine-uptime")

                    # Chat Status card: ring, name, and the running/idle split.
                    with Horizontal(classes="engine-readout"):
                        yield Label("0/0", id="metric-threads-ring", classes="engine-ring")
                        yield Label("THREADS", id="metric-threads-label", classes="engine-name")
                        yield Label("0 Running · 0 Idle", id="metric-threads-detail", classes="engine-detail")

                    # Per-card segment bars. The mockup draws one 10-cell bar
                    # under Swarm Status and another under Chat Status; a
                    # terminal cannot tint single cells from one Label, so
                    # each cell is wrapped in its own Rich colour tag. The
                    # compose tree is built before any slot state exists, so
                    # these render all-idle and _flush_metrics() repaints them
                    # with live state on first mount.
                    yield Label(
                        _empty_cluster_bar_markup(self._NUM_SLOTS),
                        id="metric-swarm-bar",
                        classes="cluster-bar",
                        markup=True,
                    )
                    yield Label(
                        _empty_cluster_bar_markup(self._NUM_SLOTS),
                        id="metric-threads-bar",
                        classes="cluster-bar",
                        markup=True,
                    )
                # End .engine-card

                # THREADS MATRIX: the mockup's numbered grid of thread cells
                # (01 Streaming 4m12s), one per job slot, tinted by that
                # slot's state. It is the Overview's main content, so it
                # takes the free height between the readouts above and the
                # two pinned bands below.
                yield Label("THREADS MATRIX", id="threads-matrix-label", classes="section-label")
                yield DataTable(id="threads-matrix")

                # Job slot table: carries the per-slot prompt file and exact
                # pipeline status that the matrix's one-word state does not.
                # Its column headers name the columns, so it needs no caption
                # row of its own.
                yield DataTable(id="slots-table")

                with Horizontal(classes="pane-title-compact"):
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

            # ─── Tab 2: Sessions ────────────────────────────────
            with TabPane("Sessions", id="tab-sessions"), Vertical(classes="overview-container"):
                with Horizontal(classes="card-inner"):
                    yield Label("REGISTERED", id="session-total-label", classes="section-label")
                    yield Label("0", id="session-total", classes="metric-value")
                    yield Label("HEALTHY", id="session-healthy-label", classes="section-label")
                    yield Label("0", id="session-healthy", classes="metric-ok")
                    yield Label("LIMITED", id="session-limited-label", classes="section-label")
                    yield Label("0", id="session-limited", classes="metric-value")
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
            with TabPane("Swarm", id="tab-swarm"), Vertical(classes="overview-container"):
                # Redesign v6.5.2: view-toggle row + Clear, as in the mockup.
                with Horizontal(classes="toggle-row"):
                    yield Button("Event Log", id="btn-swarm-event", classes="toggle-active")
                    yield Button("System Log", id="btn-swarm-system", classes="toggle-inactive")

                yield Label("Attachment File or Folder", classes="section-label")
                with Horizontal(classes="card-inner"):
                    yield Input(
                        value="",
                        placeholder="path/to/file or folder",
                        id="input-swarm-file",
                        classes="field-input",
                    )
                    yield Button("Browse", id="btn-browse-swarm-file", classes="btn-browse")
                with Horizontal(classes="card-inner"):
                    swarm_env = os.environ.get("QWEN_SWARM_CONCURRENCY", "").strip()
                    swarm_max = min(10, max(1, int(swarm_env))) if swarm_env.isdigit() and int(swarm_env) > 0 else 10
                    yield Button("START", variant="primary", id="btn-swarm-start")
                    yield Button("CANCEL", id="btn-swarm-cancel")
                    yield Label(f"Adaptive templates · max {swarm_max} browsers", id="swarm-summary")
                yield DataTable(id="swarm-table")
                with Horizontal(classes="pane-title"):
                    yield Label("Swarm Log", classes="field-label")
                    yield Button("🗑 Clear", id="btn-clear-swarm-log", classes="btn-copy-log", variant="default")
                    yield Button("📋 Copy", id="btn-copy-swarm-log", classes="btn-copy-log", variant="default")
                # Two stacked views; only one visible at a time. The Event
                # log holds structured slot/broadcast events; the System
                # log holds raw adapter output. Neither is a layout peer of
                # #log-view-swarm, so the containment tests are unaffected.
                yield QwenTuiRichLog(
                    id="log-view-swarm",
                    highlight=True,
                    markup=True,
                    max_lines=2000,
                    auto_scroll=True,
                    wrap=True,
                )
                system_log = QwenTuiRichLog(
                    id="log-view-swarm-system",
                    highlight=True,
                    markup=True,
                    max_lines=2000,
                    auto_scroll=True,
                    wrap=True,
                )
                # RichLog has no `display` constructor argument in Textual
                # 8.2.8, so the hidden state is applied post-construction.
                system_log.display = False
                yield system_log

            # ─── Tabs 2..N: Job Slots ───────────────────────────
            for s in range(1, self._NUM_SLOTS + 1):
                with TabPane(f"Slot {s} ●", id=f"tab-slot-{s}"), Horizontal(classes="slot-container"):
                    with ScrollableContainer(classes="left-pane"):
                        yield Static(f"[ CONFIGURATION: SLOT {s} ]", classes="pane-title")

                        yield Label("Prompt Template (Quick Select)", classes="section-label")
                        yield Select(
                            self._template_options,
                            prompt="Select a template or type file path below",
                            allow_blank=True,
                            id=f"select-template-{s}",
                        )

                        # Redesign v6.5.2: the mockup shows templates as
                        # one-tap chips. They are shortcuts that drive the
                        # same Select, so the dropdown and every existing
                        # keybinding / test keep working.
                        with Horizontal(classes="toggle-row", id=f"chip-row-{s}"):
                            for title, role in self._template_options[:4]:
                                yield Button(
                                    self._truncate_name(title, 18),
                                    id=f"chip-{s}-{role}",
                                    classes="template-chip",
                                )

                        yield Label("Prompt File / Role (Required) *", classes="section-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value="",
                                placeholder="path/to/prompt.md or role (any .md in modules/templates/)",
                                id=f"input-prompt-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-prompt-{s}", classes="btn-browse")

                        yield Label("Attachment File or Folder (Optional)", classes="section-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value="",
                                placeholder="path/to/file or folder",
                                id=f"input-file-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-file-{s}", classes="btn-browse")

                        yield Label("Output Destination", classes="section-label")
                        with Horizontal(classes="field-row"):
                            yield Input(
                                value=str(DEFAULT_OUTPUT),
                                placeholder="path/to/output.md",
                                id=f"input-output-{s}",
                                classes="field-input",
                            )
                            yield Button("Browse", id=f"btn-browse-output-{s}", classes="btn-browse")

                        with Horizontal(classes="card-inner"):
                            with Vertical(classes="toggle-label-box"):
                                yield Label("Headless Browser", classes="section-label")
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

        # Redesign v6.5.2: bottom nav dock. The mockup's dock replaces the
        # key-hint Footer: four section names at the very bottom of the
        # screen, the active one carrying the highlight. Key shortcuts
        # (alt+0, ctrl+alt+s, …) still work through the Header bindings.
        with Horizontal(id="nav-dock", classes="nav-dock"):
            yield Button("▦ OVERVIEW", id="nav-overview", classes="nav-item nav-active")
            yield Button("⚿ LOGIN", id="nav-login", classes="nav-item nav-inactive")
            yield Button("▣ CHAT", id="nav-chat", classes="nav-item nav-inactive")
            yield Button("⚯ SWARM", id="nav-swarm", classes="nav-item nav-inactive")
            # The mockup's dock carries the section names only. The keys the
            # old Footer listed stay reachable in two ways: the Help overlay
            # on `?`, and a trailing hint on the dock itself.
            yield Label("alt+0 overview · alt+1..9 slot · ctrl+alt+s swarm · ? help", classes="nav-hint")

    def on_mount(self) -> None:
        """Initialise tables, cache widget refs, and defer log startup."""
        self._init_table()
        self._init_threads_matrix()
        self._init_swarm_table()

        # P3: cache metric widget refs once; no per-call DOM lookups.
        self._metric_active = self.query_one("#metric-active", Label)
        self._metric_done = self.query_one("#metric-done", Label)
        self._metric_model = self.query_one("#metric-model", Label)
        self._metric_swarm_ring = self.query_one("#metric-swarm-ring", Label)
        self._metric_swarm_detail = self.query_one("#metric-swarm-detail", Label)
        self._metric_swarm_uptime = self.query_one("#metric-swarm-uptime", Label)
        self._metric_threads_ring = self.query_one("#metric-threads-ring", Label)
        self._metric_threads_detail = self.query_one("#metric-threads-detail", Label)
        self._metric_swarm_bar = self.query_one("#metric-swarm-bar", Label)
        self._metric_threads_bar = self.query_one("#metric-threads-bar", Label)

        # Redesign v6.5.2: seed the engine readouts so the Overview shows real
        # numbers on first paint rather than placeholders.
        self._flush_metrics()
        # Seed the bottom nav dock to match the initial tab.
        self._refresh_nav_dock()

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

        muted = THEME["muted"]
        self._log_msg(
            f"[bold {THEME['accent_fg']}]Qwen Web Automation TUI initialized with multi-slot architecture.[/]"
        )
        self._log_msg(f"[{muted}]Each slot runs an independent Chromium process sharing login state.[/]")

        # U5: seed per-slot log views with an empty-state hint.
        for s in range(1, self._NUM_SLOTS + 1):
            with contextlib.suppress(NoMatches):
                log_view = self.query_one(f"#log-view-{s}", QwenTuiRichLog)
                log_view.auto_scroll = True
                log_view.write(f"[{muted}]Set a prompt file, then press Enter or RUN.[/]")

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
