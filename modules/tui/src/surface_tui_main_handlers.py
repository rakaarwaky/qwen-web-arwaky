"""Combined TUI handler mixin — the public entry point for screen actions.

Surface layer (surface_cli): re-exports the per-concern handler mixins as the single ``_TuiHandlersMixin`` symbol that
:class:`~modules.tui.src.surface_tui_app.QwenTuiApp` binds. Each concern lives in its
own ``surface_tui_{concern}_handler.py`` file:

- ``sessions`` — Sessions pane account cards, delete flow, row keyboard nav.
- ``navlog`` — nav dock, tab/slot switching, log copy, file picker.
- ``chatlog`` — chat console prompt composer.
- ``swarm`` — Swarm screen routing and log toggle.
- ``app`` — system actions, workspace init, session setup, quit guard.
"""

from __future__ import annotations

from typing import Any

from modules.tui.src.surface_tui_app_handler import _TuiAppHandlerMixin
from modules.tui.src.surface_tui_chatlog_handler import _TuiChatLogHandlerMixin
from modules.tui.src.surface_tui_navlog_handler import _TuiNavLogHandlerMixin
from modules.tui.src.surface_tui_sessions_handler import _TuiSessionsHandlerMixin
from modules.tui.src.surface_tui_swarm_handler import _TuiSwarmHandlerMixin


class _TuiHandlersMixin(
    _TuiSessionsHandlerMixin,
    _TuiNavLogHandlerMixin,
    _TuiChatLogHandlerMixin,
    _TuiSwarmHandlerMixin,
    _TuiAppHandlerMixin,
):
    """Combined behaviour of every ``surface_tui_*_handler`` mixin."""

    # Cross-concern stubs: methods one mixin calls that another provides.
    # Declared on the combined class so mypy resolves them without each
    # split file re-declaring the others' members.
    _open_picker: Any
    _session_login_action: Any
    _ensure_sessions_loaded: Any


__all__ = ["_TuiHandlersMixin"]
