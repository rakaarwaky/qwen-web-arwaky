"""Modern-Brutalist TUI interactive controller with Tab-per-Job-Slot architecture.

Surface layer (surface_cli): Thin composition root for the Textual application.
All logic is split across focused mixin modules:

- :mod:`surface_cli_tui_compose`  — ``compose()`` UI tree + lifecycle hooks
- :mod:`surface_cli_tui_handlers` — Textual event callbacks + keyboard actions
- :mod:`surface_cli_tui_workers`  — background workers, slot run/cancel cycle
- :mod:`surface_cli_tui_utils`    — table, metrics, status badge, log helpers
- :mod:`surface_cli_tui_css`      — design tokens (``THEME``, ``TUI_CSS``)
- :mod:`surface_cli_tui_components` — ``FilePickerModal``, ``HelpScreen``, ``QwenTuiLogHandler``
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App
from textual.binding import Binding

from modules.cli.src.surface_cli_tui_components import ConfirmModal
from modules.cli.src.surface_cli_tui_compose import _TuiComposeMixin
from modules.cli.src.surface_cli_tui_css import TUI_CSS
from modules.cli.src.surface_cli_tui_handlers import _TuiHandlersMixin
from modules.cli.src.surface_cli_tui_utils import _TuiUtilsMixin
from modules.cli.src.surface_cli_tui_workers import _TuiWorkersMixin
from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import ISlotRunPlanProtocol, IWorkspaceProtocol
from modules.shared.src.contract_session_aggregate import ISessionManagerProtocol
from modules.shared.src.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.taxonomy_core_constant import DEFAULT_MAX_WORKERS
from modules.shared.src.taxonomy_swarm_vo import SwarmId
from modules.shared.src.utility_core_prompt_template import prompt_template_manifest
from modules.shared.src.utility_core_version import get_package_version

NUM_SLOTS = max(2, int(DEFAULT_MAX_WORKERS))

# Textual alt-chords only support a single digit (alt+0..9). Slots beyond 9
# fall back to ctrl+alt chords. alt+0 is reserved for the Overview tab.
_EXTRA_SLOT_KEYS: dict[int, str] = {s: f"ctrl+alt+{s - 10}" for s in range(10, 20)}

_APP_VERSION = get_package_version()


class QwenTuiApp(
    _TuiComposeMixin,
    _TuiHandlersMixin,
    _TuiWorkersMixin,
    _TuiUtilsMixin,
    App[None],
):
    """Obsidian Nebula Terminal User Interface for Qwen Web Automation with Tab-per-Job-Slot."""

    CSS = TUI_CSS
    TITLE = f"QWEN-CLI {_APP_VERSION} "
    SUB_TITLE = "chat.qwen.ai parallel automation engine"

    # alt+0 → Overview, alt+1..9 → Slot 1..9, ctrl+alt+0..9 → Slots 10..19.
    BINDINGS = [
        Binding("alt+0", "switch_tab_overview", "Overview"),
        Binding("ctrl+alt+s", "switch_tab_swarm", "Swarm"),
        *[
            Binding(
                f"alt+{s}" if s <= 9 else _EXTRA_SLOT_KEYS[s],
                f"switch_tab_slot({s})",
                f"Slot {s}",
            )
            for s in range(1, NUM_SLOTS + 1)
        ],
        Binding("enter", "run_active_slot", "Run Slot"),
        Binding("ctrl+r", "run_active_slot", "Run"),
        Binding("ctrl+x", "cancel_active_slot", "Cancel Slot"),  # A8
        Binding("ctrl+c", "copy_active_log", "Copy Log"),
        Binding("ctrl+l", "login_action", "Login"),
        Binding("ctrl+i", "init_action", "Init"),
        Binding("ctrl+q", "request_quit", "Quit"),
        Binding("escape", "request_quit", "Exit"),
        Binding("question_mark", "show_help", "Help"),  # A3
        # A4: sequential tab cycling for slots >= 10 or keyboard convenience
        Binding("alt+left", "prev_slot", "Prev Slot"),
        Binding("alt+right", "next_slot", "Next Slot"),
    ]

    # Consumed by _TuiComposeMixin and _TuiUtilsMixin.
    _NUM_SLOTS: int = NUM_SLOTS

    def __init__(
        self,
        workspace: IWorkspaceProtocol,
        direct: IDirectPromptAggregate,
        file_only: IPromptFileAggregate,
        attachment: IAttachmentPromptAggregate,
        slot_config: ISlotRunPlanProtocol,
        setup: ISetupAggregate | None = None,
        session: ISessionAggregate | None = None,
        jobs: IJobManagerAggregate | None = None,
        swarm: ISwarmAggregate | None = None,
        session_manager: ISessionManagerProtocol | None = None,
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._direct = direct
        self._file_only = file_only
        self._attachment = attachment
        self._setup = setup
        self._session = session
        self._jobs = jobs
        self._swarm = swarm
        self._session_manager = session_manager
        self._swarm_id: SwarmId | None = None
        # AR-1: TUI slot config is injected from the Root container, never
        # imported from Capabilities directly.
        self._slot_config = slot_config
        self._target_field_for_picker: str | None = None
        self._slot_workers: dict[int, Any] = {}
        # AR-2/FE-1: per-slot cancel events isolate concurrent runs.
        self._slot_cancel_events: dict[int, Any] = {}
        self._slot_stats: dict[int, dict[str, Any]] = {
            s: {"status": "IDLE", "file": "-", "duration": 0.0} for s in range(1, NUM_SLOTS + 1)
        }
        # C5: build template options / roles once instead of per-compose.
        # Roles are discovered dynamically from modules/templates/*.md, so a
        # new template file added to that folder shows up here with no code change.
        manifest = prompt_template_manifest()
        self._template_options: list[tuple[str, str]] = [(meta["title"], role) for role, meta in manifest.items()]
        self._template_roles: set[str] = set(manifest)
        # P3: widget refs cached at mount time.
        self._metric_active: Any = None
        self._metric_done: Any = None
        # U4: session-check timeout flag.
        self._session_check_timed_out: bool = False
        # UX-4-2: last resolved session state (VALID/EXPIRED/TIMEOUT) or None
        # while still checking.
        self._last_session_state: str | None = None
        # P4: debounce metrics refresh — at most 4 updates/sec.
        self._metrics_pending: bool = False
        # A4: timestamp of last Escape press for double-escape quit guard.
        self._last_esc_time: float = 0.0
        # C4: initialize login guard flag eagerly (was only set in worker finally block).
        self._login_in_flight: bool = False
        # U7: generation token per-slot to guard _finalize_slot against stale workers.
        self._slot_generation: dict[int, int] = {s: 0 for s in range(1, NUM_SLOTS + 1)}
        # Issue #277: input held while the Swarm resource modal is up.
        self._swarm_pending_input: Path | None = None

    # ── Swarm resource-governance presentation (issue #277) ────────────────────
    # Lives on the App so the Workers mixin stays within its AES406
    # control-flow budget. Below the threshold a Swarm starts immediately; at
    # or above it, ConfirmModal asks the user to confirm the fan-out first.
    def _confirm_or_start_swarm(self, input_path: Path) -> None:
        """Start the Swarm, presenting a resource warning modal when needed."""
        warning = getattr(self._swarm, "resource_warning", None)
        if warning is None:
            self._swarm_pending_input = None
            self._swarm_worker(input_path)
            return
        self.push_screen(
            ConfirmModal(
                title="Swarm Resource Usage",
                message=warning,
                confirm_label="Start Swarm",
            ),
            callback=self._on_swarm_confirmed,
        )

    def _on_swarm_confirmed(self, confirmed: bool) -> None:
        """Launch the held Swarm only when the user confirmed the modal."""
        pending = self._swarm_pending_input
        self._swarm_pending_input = None
        if not confirmed or pending is None:
            return
        self._swarm_worker(pending)


__all__ = [
    "QwenTuiApp",
]
