"""Compose and lifecycle methods for the Qwen TUI application.

Surface layer (surface_cli): Mixin providing the ``compose`` UI tree and
lifecycle hooks (``on_mount``, ``on_unmount``, ``_deferred_startup``).
Imported by :class:`~modules.cli.src.surface_cli_tui_app.QwenTuiApp`.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    LoadingIndicator,
    Static,
    TabbedContent,
    TabPane,
)

from modules.cli.src.surface_cli_tui_components import QwenTuiLogHandler, QwenTuiRichLog
from modules.cli.src.surface_cli_tui_css import THEME
from modules.cli.src.surface_cli_tui_utils import _empty_cluster_bar_markup
from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL
from modules.shared.src.utility_core_version import get_package_version

# Widget ID shared between compose (widget creation) and handlers (query).
JOBS_TABLE_ID = "jobs-table"


class _TuiComposeMixin:
    """Mixin that owns the Textual compose tree and app lifecycle hooks."""

    # QwenTuiApp sets these at class level / __init__; the mixin reads them.
    _NUM_SLOTS: int
    _slot_workers: dict[int, Any]
    _template_options: list[tuple[str, str]]
    # Declared here to match _TuiUtilsMixin and avoid incompatible-definition error.
    _log_handler: logging.Handler

    # Stubs for methods provided by other mixins / App at runtime.
    query_one: Any
    set_timer: Any
    _log_msg: Any
    _check_session: Any
    _format_status: Any
    _truncate_name: Any
    _flush_metrics: Any
    _refresh_metrics: Any
    _refresh_slot_chips: Any
    _refresh_nav_dock: Any
    _override_hint: Any
    _override_rows: Any
    _override_badge: Any
    _override_display: Any

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
        # Design parity: no separate Top Bar. The brand row lives inside the
        # page canvas and matches the mockup's fixed header markup.
        with TabbedContent(id="main-tabs"):
            # ─── Screen 1: Overview ──────────────────────────────
            with TabPane("Overview", id="tab-overview"), Vertical(classes="overview-container"):
                # In-page brand row (replaces the docked Header bar).
                with Horizontal(classes="app-brand-row"):
                    yield Label(">_ QWEN-CLI", classes="app-brand-title")
                    yield Label(f"v{get_package_version()}", classes="app-brand-version")
                # Every Overview block lives in one scroll band, in the
                # mockup's order: telemetry banner, swarm card, chat card, log
                # card. The band is the only element that gives up rows on a
                # short terminal, so the log panel keeps its height at every
                # size — tests/unit_tui_log_containment.py and
                # tests/unit_surface_cli_tui_app.py both gate on that.
                with Vertical(id="overview-cards", classes="overview-scroll"):
                    # Telemetry banner: two raised tiles, the mockup's
                    # ACTIVE ACCOUNTS count and the routed model name.
                    with Vertical(classes="screen-card metric-card"), Horizontal(classes="metric-tiles"):
                        with Vertical(classes="metric-tile"):
                            yield Label(
                                "● ACTIVE ACCOUNTS",
                                id="metric-active-label",
                                classes="metric-tile-label",
                            )
                            with Horizontal(classes="metric-tile-value"):
                                yield Label("0", id="metric-active", classes="metric-tile-number")
                                yield Label("Active", classes="metric-tile-unit")
                        with Vertical(classes="metric-tile metric-tile-model"):
                            yield Label("⊕ MODEL", id="metric-model-label", classes="metric-tile-label")
                            yield Label(
                                DEFAULT_MODEL,
                                id="metric-model",
                                classes="metric-tile-number metric-tile-model-value",
                            )

                    # Swarm Status card: icon chip + title, the inset bento
                    # (ring, state, uptime) and the per-slot cluster bar.
                    with Vertical(classes="screen-card engine-card"):
                        with Horizontal(classes="card-title-row"):
                            yield Static("⌬", classes="card-icon")
                            yield Label("Swarm Status", id="metric-swarm-label", classes="card-title")
                        with Horizontal(classes="engine-bento"):
                            yield Label("0/0", id="metric-swarm-ring", classes="engine-ring")
                            yield Label("Idle", id="metric-swarm-detail", classes="engine-detail")
                            yield Static("", classes="engine-spacer")
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

                    # Chat / Threads Status card: same shape, no uptime block.
                    with Vertical(classes="screen-card engine-card"):
                        with Horizontal(classes="card-title-row"):
                            yield Static("💬", classes="card-icon")
                            yield Label("Chat Status", id="metric-threads-label", classes="card-title")
                        with Horizontal(classes="engine-bento"):
                            yield Label("0/0", id="metric-threads-ring", classes="engine-ring")
                            with Vertical(classes="engine-body"):
                                yield Label("Active Threads", classes="engine-sub")
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

                    # System Event Log: the mockup's bordered card with a
                    # LIVE STREAM marker. The Copy button stays because
                    # action_copy_active_log is bound to it.
                    with Vertical(classes="screen-card log-card"):
                        with Horizontal(classes="log-card-head"):
                            yield Static("●", classes="log-pip log-pip-live")
                            yield Label("[ SYSTEM EVENT LOG ]", classes="log-card-title", markup=False)
                            yield Static("", classes="log-head-spacer")
                            yield Static("●", classes="log-pip log-pip-stream")
                            yield Label("LIVE STREAM", classes="log-live-label")
                            yield Button(
                                "Copy",
                                id="btn-copy-log",
                                classes="btn-copy-log",
                                variant="default",
                            )
                        yield QwenTuiRichLog(
                            id="log-view-overview",
                            highlight=True,
                            markup=True,
                            max_lines=2000,
                            auto_scroll=True,
                            wrap=True,
                        )

            # ─── Screen 2: Login / Session Manager ───────────────
            with TabPane("Sessions", id="tab-sessions"), Vertical(classes="screen-body"):
                with Horizontal(classes="app-brand-row"):
                    yield Label(">_ QWEN-CLI", classes="app-brand-title")
                    yield Label(f"v{get_package_version()}", classes="app-brand-version")
                # SESSION POOL STATUS card: three stacked metric tiles.
                with Vertical(classes="screen-card"):
                    with Horizontal(classes="pane-title"):
                        yield Label("▤ SESSION POOL STATUS", id="session-pool-title", classes="field-label")
                    with Horizontal(classes="login-metric-row login-metric-grid"):
                        for label_text, label_id, value_id, value_cls in (
                            ("REGISTERED", "session-total-label", "session-total", "login-metric-value"),
                            ("ACTIVE", "session-healthy-label", "session-healthy", "login-metric-ok"),
                            ("LIMITED", "session-limited-label", "session-limited", "login-metric-value"),
                        ):
                            with Vertical(classes="login-metric-cell"):
                                yield Label(label_text, id=label_id, classes="login-metric-label")
                                yield Label("0", id=value_id, classes=value_cls)

                # Full-width ADD ACCOUNT button.
                yield Button(
                    "⊕ ADD ACCOUNT",
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
                    yield Label("· ·", classes="field-label")
                    yield Button(
                        "↻ Re-check Tokens",
                        id="btn-sessions-refresh",
                        classes="btn-ghost",
                        variant="default",
                    )

                # Named-account login row: pick the account name, then run the
                # in-process headed login that registers it in the pool.
                with Horizontal(classes="toggle-row"):
                    yield Input(
                        placeholder="account name (e.g. work)",
                        id="input-sessions-name",
                        classes="field-label",
                        max_length=64,
                    )
                    yield Button(
                        "🔐 Add Account",
                        id="btn-sessions-login",
                        classes="btn-sessions-login",
                        variant="primary",
                    )

                # Account cards container.
                yield Label("Registered Sessions", classes="field-label")
                with Vertical(id="account-cards", classes="screen-card"):
                    yield Label("No accounts registered.", id="account-empty", classes="field-label")
                yield DataTable(id="sessions-table")

                with Horizontal(classes="toggle-row"):
                    yield Button(
                        "🔄 Refresh",
                        id="btn-sessions-rerefresh",
                        classes="btn-sessions-refresh",
                        variant="default",
                    )
                    yield Button(
                        "🔐 Add Session",
                        id="btn-sessions-login",
                        classes="btn-sessions-login",
                        variant="primary",
                    )
                    yield Button(
                        "🏥 Health Check",
                        id="btn-sessions-health",
                        classes="btn-sessions-health",
                        variant="default",
                    )
                yield QwenTuiRichLog(
                    id="log-view-sessions",
                    highlight=True,
                    markup=True,
                    max_lines=500,
                    auto_scroll=True,
                    wrap=True,
                )

            # ─── Screen 3: Chat (per-slot console) ─────────────────
            # The mockup's chat console carries no configuration form: it is a
            # slot carousel, a transcript, the slot's event log, three action
            # pills, and a composer. The form moved to the Settings pane below,
            # so every widget id the run/cancel workers resolve still exists.
            for s in range(1, self._NUM_SLOTS + 1):
                with TabPane(f"Slot {s} ●", id=f"tab-slot-{s}"), Vertical(classes="chat-screen"):
                    with Horizontal(classes="app-brand-row"):
                        yield Label(">_ QWEN-CLI", classes="app-brand-title")
                        yield Label(f"v{get_package_version()}", classes="app-brand-version")
                    # Horizontal slot picker: one pill per job slot, this pane's
                    # own slot filled — the mockup's SLOT 01 … SLOT 10 row.
                    with Horizontal(classes="slot-carousel"):
                        for i in range(1, self._NUM_SLOTS + 1):
                            yield Button(
                                f"● SLOT {i:02d}",
                                id=f"chat-slot-{s}-{i}",
                                classes="slot-chip slot-chip-active" if i == s else "slot-chip",
                            )

                    # Telemetry header: Event/System switch, live badge, beacon.
                    with Horizontal(classes="telemetry-header"):
                        with Horizontal(classes="seg-switch"):
                            yield Button("Event Log", id=f"btn-slot-event-{s}", classes="seg-btn seg-active")
                            yield Button("System Log", id=f"btn-slot-system-{s}", classes="seg-btn")
                        yield Static("", classes="telemetry-spacer")
                        yield Label(
                            self._format_status("IDLE", "badge"),
                            id=f"status-badge-{s}",
                            classes="status-badge",
                        )
                        yield Label("●", id=f"live-beacon-{s}", classes="live-beacon")

                    # Transcript: prompts right-aligned, answers left-aligned.
                    with ScrollableContainer(classes="chat-stream", id=f"chat-scroll-{s}"):
                        yield Static(
                            "Pick a prompt file, or type a task below to get started.",
                            id=f"chat-transcript-{s}",
                            classes="chat-hint",
                        )

                    # Event log block: mockup's "EVENT LOG [SLOT #N]" card.
                    with Vertical(classes="event-log-card"):
                        with Horizontal(classes="event-log-head"):
                            yield Label("EVENT LOG", classes="event-log-title")
                            yield Label(f"[SLOT #{s}]", classes="event-log-slot")
                            yield LoadingIndicator(id=f"loading-{s}", classes="slot-loading")
                            yield Button(
                                "Copy",
                                id=f"btn-copy-log-{s}",
                                classes="btn-copy-log",
                                tooltip="Copy slot log",
                            )
                        yield QwenTuiRichLog(
                            id=f"log-view-{s}",
                            highlight=True,
                            markup=True,
                            classes="slot-log-view",
                            max_lines=2000,
                            wrap=True,
                        )
                        system_log = QwenTuiRichLog(
                            id=f"log-view-{s}-system",
                            highlight=True,
                            markup=True,
                            classes="slot-log-view",
                            max_lines=1000,
                            wrap=True,
                        )
                        system_log.display = False
                        yield system_log
                        yield Label("--:--:--", id=f"slot-log-time-{s}", classes="slot-log-time")

                    # Action pill row: design/slot_chat_automation_console bottom dock.
                    with Horizontal(classes="action-pill-row"):
                        yield Button(
                            "⬆ Prompt",
                            id=f"btn-pill-prompt-{s}",
                            classes="action-pill",
                        )
                        yield Button(
                            "📎 Attach",
                            id=f"btn-pill-attach-{s}",
                            classes="action-pill",
                        )
                        yield Button(
                            "✨ Templates",
                            id=f"btn-pill-templates-{s}",
                            classes="action-pill action-pill-templates",
                        )
                        yield Button(
                            "⬛ HEADLESS ON",
                            id=f"btn-headless-{s}",
                            classes="action-pill action-pill-headless",
                        )
                    # File indicator: shows the attached file/folder, hidden by default.
                    file_indicator = Label("", id=f"file-indicator-{s}", classes="file-indicator")
                    file_indicator.display = False
                    yield file_indicator
                    # Composer: prompt glyph, free-text task, send button.
                    with Horizontal(classes="composer"):
                        yield Label(">", classes="composer-glyph")
                        yield Input(
                            value="",
                            placeholder="Type automated task or command...",
                            id=f"composer-{s}",
                            classes="composer-input",
                        )
                        yield Button("Send", id=f"btn-send-{s}", classes="btn-send")

            # ─── Screen 4: Swarm ─────────────────────────────────
            # design/swarm_multi_agent_stream: attachment card, view toggle,
            # one log card (path header + Clear, the stream, the socket
            # footer) and the Stop/RESTART deck. The mockup has no agent
            # table, so per-agent state is reported to the log instead.
            with TabPane("Swarm", id="tab-swarm"), Vertical(classes="swarm-screen"):
                with Horizontal(classes="app-brand-row"):
                    yield Label(">_ QWEN-CLI", classes="app-brand-title")
                    yield Label(f"v{get_package_version()}", classes="app-brand-version")

                # Attachment card: resolved file on the left, Browse chip right.
                with Horizontal(classes="screen-card swarm-file-card"):
                    yield Label("▤", id="swarm-file-icon", classes="swarm-file-icon")
                    yield Label("No file attached", id="swarm-file-name", classes="swarm-file-name")
                    yield Button(
                        "⇪ Browse",
                        id="btn-browse-swarm-file",
                        classes="swarm-browse-chip",
                    )

                # View toggle: OUTPUT INSPECTION caption, switch on the right.
                with Horizontal(classes="output-inspection"):
                    yield Label("OUTPUT INSPECTION", classes="card-caption")
                    with Horizontal(classes="seg-switch swarm-seg"):
                        yield Button(
                            "Event Log",
                            id="btn-swarm-event",
                            classes="seg-btn seg-active",
                        )
                        yield Button(
                            "log system",
                            id="btn-swarm-system",
                            classes="seg-btn",
                        )

                # Log card. Both streams live in this one panel, so the toggle
                # swaps them in place and the card keeps its height.
                with Vertical(classes="screen-card swarm-log-card"):
                    with Horizontal(classes="swarm-log-head"):
                        yield Label(
                            "/var/log/qwen-swarm.pool.log",
                            classes="swarm-log-path",
                        )
                        yield Button(
                            "🗑 Clear",
                            id="btn-clear-swarm-log",
                            classes="swarm-clear-chip",
                        )
                    yield QwenTuiRichLog(
                        id="log-view-swarm",
                        highlight=True,
                        markup=True,
                        classes="swarm-log-view",
                        max_lines=2000,
                        auto_scroll=True,
                        wrap=True,
                    )
                    system_log = QwenTuiRichLog(
                        id="log-view-swarm-system",
                        highlight=True,
                        markup=True,
                        classes="swarm-log-view",
                        max_lines=2000,
                        auto_scroll=True,
                        wrap=True,
                    )
                    system_log.display = False
                    yield system_log
                    with Horizontal(classes="swarm-log-foot"):
                        yield Label(">", classes="swarm-caret")
                        yield Label(
                            "Listening on unix socket /run/qwen-swarm.sock...",
                            id="listener-line",
                            classes="listener-line",
                        )

                # Action deck: Stop on the left, the primary on the right.
                with Horizontal(classes="swarm-action-deck"):
                    yield Button(
                        "■ Stop",
                        id="btn-swarm-cancel",
                        classes="btn-stop",
                    )
                    yield Button(
                        "⬛ HEADLESS ON",
                        id="btn-headless-swarm",
                        classes="swarm-headless-toggle",
                    )
                    yield Button(
                        "↻ RESTART",
                        id="btn-swarm-start",
                        classes="btn-restart",
                    )

                # Input field (read by _run_swarm; hidden by design — the
                # Browse chip in the swarm-file-card above drives the value).
                swarm_input = Input(
                    value="",
                    placeholder="path/to/file or folder",
                    id="input-swarm-file",
                    classes="swarm-file-input",
                )
                swarm_input.display = False
                yield swarm_input

            # ─── Screen 5: Settings ──────────────────────────────
            # The Settings pane is the runtime-override surface: one row per
            # registered environment value, Apply/Reset per row. No mockup
            # ships for this screen, so it follows the same card language as
            # the Overview and Swarm consoles. An earlier draft carried a
            # per-slot job form here; it read inputs that only lived on this
            # screen and shadowed the Chat console's composer, so the form is
            # gone and overrides are the whole pane.
            with TabPane("Settings", id="tab-settings"), Vertical(classes="settings-screen"):
                with Horizontal(classes="app-brand-row"):
                    yield Label(">_ QWEN-CLI", classes="app-brand-title")
                    yield Label(f"v{get_package_version()}", classes="app-brand-version")

                # RUNTIME OVERRIDES: one row per registered environment value.
                override_scroll = ScrollableContainer(id="settings-overrides", classes="override-scroll")
                with override_scroll:
                    override_card = Vertical(classes="screen-card settings-card override-card", id="override-card")
                    with override_card:
                        with Horizontal(classes="card-title-row"):
                            yield Static("⚙", classes="card-icon")
                            yield Label("RUNTIME OVERRIDES", classes="card-title")

                        yield Label(
                            "Every value here already has a working default. Clear a field to fall back to it.",
                            classes="override-blurb",
                        )
                        yield Label(self._override_hint(), classes="override-hint")
                        for name, purpose, default, secret in self._override_rows():
                            suffix = name.replace("-", "_")
                            badge_text, badge_class = self._override_badge(name)
                            detail = purpose if secret else f"{purpose} · default: {default}"
                            with Vertical(classes="override-row", id=f"override-row-{suffix}"):
                                with Horizontal(classes="override-head"):
                                    yield Label(name, classes="override-name")
                                    yield Static(badge_text, classes=badge_class, id=f"override-badge-{suffix}")
                                yield Label(detail, classes="override-purpose")
                                with Horizontal(classes="override-field-row"):
                                    yield Input(
                                        value=self._override_display(name),
                                        placeholder="default",
                                        password=secret,
                                        id=f"override-input-{suffix}",
                                        classes="override-input",
                                    )
                                    yield Button("Apply", id=f"override-apply-{name}", classes="btn-apply")
                                    yield Button("Reset", id=f"override-reset-{name}", classes="btn-apply btn-reset")

                # System Actions card: doctor, update, and jobs management.
                with Vertical(classes="screen-card settings-card system-actions-card", id="system-actions-card"):
                    with Horizontal(classes="card-title-row"):
                        yield Static("🛠", classes="card-icon")
                        yield Label("SYSTEM ACTIONS", classes="card-title")

                    with Horizontal(classes="toggle-row"):
                        yield Button("🏥 Run Doctor", id="btn-tui-doctor", classes="btn-doctor")
                        yield Button("🔄 Update", id="btn-tui-update", classes="btn-update")
                        yield Button("🧹 Cleanup Jobs", id="btn-tui-jobs-cleanup", classes="btn-jobs-cleanup")

                # Jobs table card.
                with Vertical(classes="screen-card settings-card jobs-card", id="jobs-card"):
                    with Horizontal(classes="card-title-row"):
                        yield Static("⚡", classes="card-icon")
                        yield Label("BACKGROUND JOBS", classes="card-title")
                    yield DataTable(id=JOBS_TABLE_ID)
                    with Horizontal(classes="toggle-row"):
                        yield Button("↻ Refresh", id="btn-jobs-refresh", classes="btn-jobs-refresh")

        # ─── Bottom Nav Dock ───────────────────────────────────────────────
        # The mockup docks icon-over-label cells across the full width with no
        # key-hint line. The strip above them holds the active marker: a short
        # accent bar centred over the active cell, the way the mockup draws it
        # instead of a full-width hairline. Each bar cell is 1fr, so it lines
        # up with the button below it.
        with Horizontal(id="nav-dock", classes="nav-dock"):
            with Horizontal(classes="nav-bar-strip"):
                yield Static("━━━", id="nav-bar-overview", classes="nav-bar nav-bar-active")
                yield Static("", id="nav-bar-login", classes="nav-bar")
                yield Static("", id="nav-bar-chat", classes="nav-bar")
                yield Static("", id="nav-bar-swarm", classes="nav-bar")
                yield Static("", id="nav-bar-settings", classes="nav-bar")
            with Horizontal(classes="nav-items"):
                yield Button("▦\nOVERVIEW", id="nav-overview", classes="nav-item nav-active")
                yield Button("⚿\nLOGIN", id="nav-login", classes="nav-item nav-inactive")
                yield Button("▣\nCHAT", id="nav-chat", classes="nav-item nav-inactive")
                yield Button("⚯\nSWARM", id="nav-swarm", classes="nav-item nav-inactive")
                yield Button("⚙\nSETTINGS", id="nav-settings", classes="nav-item nav-inactive")

    def on_mount(self) -> None:
        """Initialise tables, cache widget refs, and defer log startup."""

        # P3: cache metric widget refs once; no per-call DOM lookups.
        self._metric_active = self.query_one("#metric-active", Label)
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
        self._refresh_slot_chips()
        # Seed the bottom nav dock to match the initial tab.
        self._refresh_nav_dock()

        # P1: cache RichLog widget refs at mount time — hot render path.
        self._log_views: dict[int, QwenTuiRichLog] = {}
        with contextlib.suppress(NoMatches):
            self._log_views[0] = self.query_one("#log-view-overview", QwenTuiRichLog)
        with contextlib.suppress(NoMatches):
            self._log_views[-1] = self.query_one("#log-view-swarm", QwenTuiRichLog)

        # Mockup parity: each chat console caches its transcript container, its
        # system-log twin, its clock label, and the empty-state hint that the
        # first message replaces. All four sit on the per-slot hot paths, so
        # they are resolved once here instead of per write.
        self._system_log_views: dict[int, QwenTuiRichLog] = {}
        self._chat_scrolls: dict[int, ScrollableContainer] = {}
        self._chat_hints: dict[int, Static] = {}
        self._slot_log_times: dict[int, Label] = {}
        for s in range(1, self._NUM_SLOTS + 1):
            with contextlib.suppress(NoMatches):
                self._log_views[s] = self.query_one(f"#log-view-{s}", QwenTuiRichLog)
            with contextlib.suppress(NoMatches):
                self._system_log_views[s] = self.query_one(f"#log-view-{s}-system", QwenTuiRichLog)
            with contextlib.suppress(NoMatches):
                self._chat_scrolls[s] = self.query_one(f"#chat-scroll-{s}", ScrollableContainer)
            with contextlib.suppress(NoMatches):
                self._chat_hints[s] = self.query_one(f"#chat-transcript-{s}", Static)
            with contextlib.suppress(NoMatches):
                self._slot_log_times[s] = self.query_one(f"#slot-log-time-{s}", Label)

        # P5: defer RichLog writes until after first paint to avoid overlay glitch.
        self.set_timer(0.4, self._deferred_startup)
        # The first Resize lands before layout, so the slot pills get one more
        # pass once their carousel has a measured width.
        self.set_timer(0.1, self._refresh_slot_chips)

    def on_resize(self, _event: events.Resize) -> None:
        """Re-tint the cluster bars once the layout has measured them.

        Each bar is a single Label whose segment widths come from the bar's
        own column count, and that count only exists after the first layout
        pass — and changes whenever the terminal is resized. The repaint is
        routed through the debounced metrics flush, so a drag-resize repaints
        once at the end instead of on every column. The slot pills are
        relabelled here too: their full "SLOT 07" captions only fit a wide
        row, so a narrower terminal gets the compact form.
        """
        self._refresh_metrics()
        self._refresh_slot_chips()

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

        # U5: the per-slot event logs start empty — the transcript hint above
        # carries the empty-state guidance, so nothing is seeded here beyond
        # the auto-scroll the streaming path depends on.
        for s in range(1, self._NUM_SLOTS + 1):
            with contextlib.suppress(NoMatches):
                log_view = self.query_one(f"#log-view-{s}", QwenTuiRichLog)
                log_view.auto_scroll = True

        self._check_session()

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
