"""Compose and lifecycle methods for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing the ``compose`` UI tree and
lifecycle hooks (``on_mount``, ``on_unmount``, ``_deferred_startup``).
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import logging
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
        """Build the four-screen layout: Overview, Login, Chat (slots), Swarm.

        A single ``TabbedContent`` carries all sections as tab panes so the
        bottom nav dock and existing handlers/tests continue to resolve it
        via ``query_one(TabbedContent)`` (singular, by class). The CHAT pane
        is the current per-slot tab layout — the nav dock's Chat button
        routes to the active slot tab.

        Widget IDs from the pre-redesign tree are preserved verbatim so
        workers, handlers, and ``tests/unit_tui_log_containment.py`` keep
        resolving without changes.
        """
        yield Header(show_clock=True)
        with TabbedContent(id="main-tabs"):
            # ─── Screen 1: Overview ──────────────────────────────
            with TabPane("Overview", id="tab-overview"), Vertical(classes="overview-container"):
                # The engine cards and the THREADS MATRIX live in their own
                # scroll band. The System Event Log strip stays outside it so
                # the panel keeps real estate on short terminals —
                # tests/unit_tui_log_containment.py and
                # tests/unit_surface_cli_tui_app.py both gate on the log
                # staying inside the tab pane at every size.
                with Vertical(id="overview-cards", classes="overview-scroll"):
                    # Top telemetry banner: ACTIVE ACCOUNTS + MODEL tiles.
                    with Vertical(classes="screen-card"), Horizontal(classes="login-metric-row"):
                        yield Label("● ACTIVE", id="metric-active-label", classes="login-metric-label")
                        yield Label("0", id="metric-active", classes="login-metric-value")
                        yield Label("│", classes="metric-divider")
                        yield Label("MODEL", id="metric-model-label", classes="login-metric-label")
                        yield Label(DEFAULT_MODEL, id="metric-model", classes="login-metric-value")
                        yield Label("│", classes="metric-divider")
                        yield Label("SLOTS", id="metric-slots-label", classes="login-metric-label")
                        yield Label(f"{self._NUM_SLOTS}", id="metric-slots", classes="login-metric-value")
                        yield Label("│", classes="metric-divider")
                        yield Label("DONE", id="metric-done-label", classes="login-metric-label")
                        yield Label("0", id="metric-done", classes="login-metric-value")
                        yield Label("│", classes="metric-divider")
                        yield Label("SESSION", id="metric-session-label", classes="login-metric-label")
                        yield Label("CHECKING…", id="session-badge", classes="login-metric-value")

                    # Swarm Status card: ring, name, detail, uptime.
                    with Vertical(classes="screen-card"):
                        with Horizontal(classes="engine-readout"):
                            yield Label("0/0", id="metric-swarm-ring", classes="engine-ring")
                            yield Label("SWARM", id="metric-swarm-label", classes="engine-name")
                            yield Label("Idle", id="metric-swarm-detail", classes="engine-detail")
                            yield Label(
                                "Uptime Elapsed —",
                                id="metric-swarm-uptime",
                                classes="engine-uptime",
                            )
                        yield Label(
                            _empty_cluster_bar_markup(self._NUM_SLOTS),
                            id="metric-swarm-bar",
                            classes="cluster-bar",
                            markup=True,
                        )

                    # Chat / Threads Status card: ring, name, running/idle split.
                    with Vertical(classes="screen-card"):
                        with Horizontal(classes="engine-readout"):
                            yield Label("0/0", id="metric-threads-ring", classes="engine-ring")
                            yield Label("THREADS", id="metric-threads-label", classes="engine-name")
                            yield Label(
                                "0 Running · 0 Idle",
                                id="metric-threads-detail",
                                classes="engine-detail",
                            )
                        yield Label(
                            _empty_cluster_bar_markup(self._NUM_SLOTS),
                            id="metric-threads-bar",
                            classes="cluster-bar",
                            markup=True,
                        )

                    # THREADS MATRIX.
                    yield Label("THREADS MATRIX", id="threads-matrix-label", classes="section-label")
                    yield DataTable(id="threads-matrix")

                    # Job slot table: per-slot prompt file and exact status.
                    yield DataTable(id="slots-table")

                # System Event Log strip (pinned below the scroll band).
                with Horizontal(classes="pane-title-compact"):
                    yield Label("System Event Log", classes="field-label")
                    yield Button("Copy", id="btn-copy-log", classes="btn-copy-log", variant="default")
                yield QwenTuiRichLog(
                    id="log-view-overview",
                    highlight=True,
                    markup=True,
                    max_lines=2000,
                    auto_scroll=True,
                    wrap=True,
                )
                yield Static(
                    "[dim]Press ? for keyboard shortcuts. Configure a slot tab, then press Enter to run.[/dim]",
                    classes="metric-item",
                )

            # ─── Screen 2: Login / Session Manager ───────────────
            with TabPane("Sessions", id="tab-sessions"), Vertical(classes="screen-body"):
                # SESSION POOL STATUS card (dns icon + 3-cell grid).
                with Vertical(classes="screen-card"):
                    with Horizontal(classes="pane-title"):
                        yield Label("dns SESSION POOL STATUS", id="session-pool-title", classes="field-label")
                    with Horizontal(classes="login-metric-row"):
                        yield Label("REGISTERED", id="session-total-label", classes="login-metric-label")
                        yield Label("0", id="session-total", classes="login-metric-value")
                        yield Label("HEALTHY", id="session-healthy-label", classes="login-metric-label")
                        yield Label("0", id="session-healthy", classes="login-metric-ok")
                        yield Label("LIMITED", id="session-limited-label", classes="login-metric-label")
                        yield Label("0", id="session-limited", classes="login-metric-value")

                # Full-width ADD ACCOUNT button.
                yield Button(
                    "add account",
                    id="btn-session-add",
                    classes="btn-primary-full",
                )

                # Hidden expandable auth panel (kept empty — SessionSetupScreen
                # is pushed via the existing ctrl+l / login_action path).
                auth_panel = Vertical(id="auth-panel", classes="screen-card")
                auth_panel.display = False
                with auth_panel:
                    yield Label("Fast Auth Panel", classes="field-label")
                    with Horizontal(classes="toggle-row"):
                        yield Button("Connect", id="btn-auth-connect", variant="primary")
                        yield Button("Cancel", id="btn-auth-cancel", classes="btn-ghost")

                # Re-check Tokens row.
                with Horizontal(classes="toggle-row"):
                    yield Label("• •", classes="field-label")
                    yield Button(
                        "refresh Re-check Tokens",
                        id="btn-sessions-refresh",
                        classes="btn-ghost",
                        variant="default",
                    )

                # Account cards container.
                yield Label("Registered Sessions", classes="field-label")
                with Vertical(id="account-cards", classes="screen-card"):
                    yield Label("No accounts registered.", id="account-empty", classes="field-label")
                yield DataTable(id="sessions-table")

                with Horizontal(classes="toggle-row"):
                    yield Button("🔄 Refresh", id="btn-sessions-rerefresh", variant="default")
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

            # ─── Screen 3: Chat (per-slot tabs) ──────────────────
            for s in range(1, self._NUM_SLOTS + 1):
                with TabPane(f"Slot {s} ●", id=f"tab-slot-{s}"), Horizontal(classes="slot-container"):
                    # LEFT PANE: configuration form (preserved from v6.5.2).
                    with ScrollableContainer(classes="left-pane"):
                        yield Static(f"[ CONFIGURATION: SLOT {s} ]", classes="pane-title")

                        yield Label("Prompt Template (Quick Select)", classes="section-label")
                        yield Select(
                            self._template_options,
                            prompt="Select a template or type file path below",
                            allow_blank=True,
                            id=f"select-template-{s}",
                        )

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
                                placeholder="path/to/prompt.md or role",
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
                                yield Label(
                                    "1 independent browser in background",
                                    classes="toggle-subtext",
                                )
                            yield Switch(value=True, id=f"switch-headless-{s}")

                        yield Button(
                            f"⚡ RUN IN SLOT {s}",
                            variant="primary",
                            id=f"btn-run-{s}",
                            classes="btn-slot-run",
                        )
                        yield Button(
                            f"✕ Cancel Slot {s}",
                            id=f"btn-cancel-{s}",
                            classes="btn-slot-cancel",
                        )
                        yield Button(
                            f"↻ Retry Slot {s}",
                            id=f"btn-retry-{s}",
                            classes="btn-slot-retry",
                        )

                    # RIGHT PANE: live log view (preserved).
                    with Vertical(classes="right-pane"):
                        with Horizontal(classes="pane-title"):
                            yield Label(f"[ LIVE LOG: BROWSER #{s} ]", classes="field-label")
                            yield Label(
                                self._format_status("IDLE", "badge"),
                                id=f"status-badge-{s}",
                                classes="status-badge",
                            )
                            yield Button(
                                "Copy",
                                id=f"btn-copy-log-{s}",
                                classes="btn-copy-log",
                                tooltip="Copy slot log",
                            )
                        yield LoadingIndicator(id=f"loading-{s}", classes="slot-loading")
                        yield QwenTuiRichLog(
                            id=f"log-view-{s}",
                            highlight=True,
                            markup=True,
                            classes="slot-log-view",
                            max_lines=2000,
                            wrap=True,
                        )

            # ─── Screen 4: Swarm ─────────────────────────────────
            with TabPane("Swarm", id="tab-swarm"), Vertical(classes="overview-container"):
                # Attachment File or Folder card.
                with Vertical(classes="screen-card"), Horizontal(classes="swarm-file-card"):
                    yield Label("description", id="swarm-file-icon", classes="swarm-file-icon")
                    yield Label("No file attached", id="swarm-file-name", classes="swarm-file-name")
                    yield Button("Browse", id="btn-browse-swarm-file", classes="btn-browse")

                # Output Inspection header with segmented toggle.
                with Horizontal(classes="output-inspection"):
                    yield Label("Output Inspection", classes="card-caption")
                    with Horizontal(classes="seg-switch"):
                        yield Button(
                            "Event Log",
                            id="btn-swarm-event",
                            classes="seg-btn seg-active",
                        )
                        yield Button(
                            "System Log",
                            id="btn-swarm-system",
                            classes="seg-btn",
                        )
                    yield Label("●", id="live-beacon", classes="live-beacon")

                # Event log (visible by default).
                yield QwenTuiRichLog(
                    id="log-view-swarm",
                    highlight=True,
                    markup=True,
                    max_lines=2000,
                    auto_scroll=True,
                    wrap=True,
                )
                # System log (hidden by default).
                system_log = QwenTuiRichLog(
                    id="log-view-swarm-system",
                    highlight=True,
                    markup=True,
                    max_lines=2000,
                    auto_scroll=True,
                    wrap=True,
                )
                system_log.display = False
                yield system_log

                # Action deck: Stop / Restart.
                with Horizontal(classes="swarm-action-deck"):
                    yield Button(
                        "stop Stop",
                        id="btn-swarm-cancel",
                        classes="btn-stop",
                    )
                    yield Button(
                        "autorenew RESTART",
                        id="btn-swarm-start",
                        classes="btn-restart",
                    )

                # Listener line.
                yield Label(
                    "> Listening on unix socket /run/qwen-swarm.sock...",
                    id="listener-line",
                    classes="listener-line",
                )

                # Swarm table.
                yield DataTable(id="swarm-table")
                with Horizontal(classes="card-inner"):
                    yield Label("Adaptive templates · max 10 browsers", id="swarm-summary")

                with Horizontal(classes="pane-title"):
                    yield Label("Swarm Log", classes="field-label")
                    yield Button("Clear", id="btn-clear-swarm-log", classes="btn-copy-log", variant="default")
                    yield Button("Copy", id="btn-copy-swarm-log", classes="btn-copy-log", variant="default")

                # Input field (read by _run_swarm; hidden by design — the
                # Browse button in the swarm-file-card above drives the value).
                swarm_input = Input(
                    value="",
                    placeholder="path/to/file or folder",
                    id="input-swarm-file",
                    classes="swarm-file-input",
                )
                swarm_input.display = False
                yield swarm_input

        # ─── Bottom Nav Dock ───────────────────────────────────────────────
        with Horizontal(id="nav-dock", classes="nav-dock"):
            yield Button("▦ OVERVIEW", id="nav-overview", classes="nav-item nav-active")
            yield Button("⚿ LOGIN", id="nav-login", classes="nav-item nav-inactive")
            yield Button("▣ CHAT", id="nav-chat", classes="nav-item nav-inactive")
            yield Button("⚯ SWARM", id="nav-swarm", classes="nav-item nav-inactive")
            yield Label(
                "alt+0 overview · alt+1..9 slot · ctrl+alt+s swarm · ? help",
                classes="nav-hint",
            )

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
