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

from typing import Any

from textual.app import App
from textual.binding import Binding

from modules.cli.src.surface_cli_tui_compose import _TuiComposeMixin
from modules.cli.src.surface_cli_tui_css import TUI_CSS
from modules.cli.src.surface_cli_tui_handlers import _TuiHandlersMixin
from modules.cli.src.surface_cli_tui_utils import _TuiUtilsMixin
from modules.cli.src.surface_cli_tui_workers import _TuiWorkersMixin
from modules.core.src.capabilities_tui_slot_config import TuiSlotConfigResolver
from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IJobManagerAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
    ISetupAggregate,
)
from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_MAX_WORKERS, PROMPT_TEMPLATE_MANIFEST
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
        Binding("ctrl+l", "login_action", "Login"),
        Binding("ctrl+i", "init_action", "Init"),
        Binding("ctrl+q", "request_quit", "Quit"),
        Binding("escape", "request_quit", "Exit"),
        Binding("question_mark", "show_help", "Help"),  # A4
    ]

    # Consumed by _TuiComposeMixin and _TuiUtilsMixin.
    _NUM_SLOTS: int = NUM_SLOTS

    def __init__(
        self,
        workspace: IWorkspaceProtocol,
        direct: IDirectPromptAggregate,
        file_only: IPromptFileAggregate,
        attachment: IAttachmentPromptAggregate,
        setup: ISetupAggregate | None = None,
        session: ISessionAggregate | None = None,
        jobs: IJobManagerAggregate | None = None,
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._direct = direct
        self._file_only = file_only
        self._attachment = attachment
        self._setup = setup
        self._session = session
        self._jobs = jobs
        self._slot_config = TuiSlotConfigResolver()
        self._target_field_for_picker: str | None = None
        self._slot_workers: dict[int, Any] = {}
        self._slot_stats: dict[int, dict[str, Any]] = {
            s: {"status": "IDLE", "file": "-", "duration": 0.0} for s in range(1, NUM_SLOTS + 1)
        }
        # C5: build template options / roles once instead of per-compose.
        self._template_options: list[tuple[str, str]] = [
            (meta["title"], role) for role, meta in PROMPT_TEMPLATE_MANIFEST.items()
        ]
        self._template_roles: set[str] = set(PROMPT_TEMPLATE_MANIFEST)
        # P3: widget refs cached at mount time.
        self._metric_active: Any = None
        self._metric_done: Any = None
        # U4: session-check timeout flag.
        self._session_check_timed_out: bool = False
        # P4: debounce metrics refresh — at most 4 updates/sec.
        self._metrics_pending: bool = False


__all__ = [
    "QwenTuiApp",
]
