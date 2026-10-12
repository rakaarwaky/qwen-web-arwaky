"""qwen-web-arwaky TUI surface — Textual app, screens, and widgets.

Barrel re-export of the TUI surfaces. The TUI layer depends on the CLI
surface (doctor checks, command dispatch) but never the reverse: no file
under ``modules/cli`` imports ``modules.tui`` at module load time; the
interactive controller defers its TUI import so headless CLI paths stay
TUI-free.
"""

import modules.tui.src.surface_tui_app as surface_tui_app
import modules.tui.src.surface_tui_components as surface_tui_components
import modules.tui.src.surface_tui_compose as surface_tui_compose
import modules.tui.src.surface_tui_css as surface_tui_css
import modules.tui.src.surface_tui_events as surface_tui_events
import modules.tui.src.surface_tui_handlers as surface_tui_handlers
import modules.tui.src.surface_tui_session_setup as surface_tui_session_setup
import modules.tui.src.surface_tui_sessions_worker as surface_tui_sessions_worker
import modules.tui.src.surface_tui_settings as surface_tui_settings
import modules.tui.src.surface_tui_utils as surface_tui_utils
import modules.tui.src.surface_tui_workers as surface_tui_workers

__all__ = [
    "surface_tui_app",
    "surface_tui_components",
    "surface_tui_compose",
    "surface_tui_css",
    "surface_tui_events",
    "surface_tui_handlers",
    "surface_tui_session_setup",
    "surface_tui_sessions_worker",
    "surface_tui_settings",
    "surface_tui_utils",
    "surface_tui_workers",
]
