"""qwen-web-arwaky TUI surface — Textual app, screens, and widgets.

Barrel re-export of the TUI surfaces. The TUI layer depends on the CLI
surface (doctor checks, command dispatch) but never the reverse: no file
under ``modules/cli`` imports ``modules.tui`` at module load time; the
interactive controller defers its TUI import so headless CLI paths stay
TUI-free.
"""

import modules.tui.src.surface_tui_app_action as surface_tui_app_action
import modules.tui.src.surface_tui_app_screen as surface_tui_app_screen
import modules.tui.src.surface_tui_chatlog_action as surface_tui_chatlog_action
import modules.tui.src.surface_tui_component as surface_tui_component
import modules.tui.src.surface_tui_compose_layout as surface_tui_compose_layout
import modules.tui.src.surface_tui_css_view as surface_tui_css_view
import modules.tui.src.surface_tui_events_action as surface_tui_events_action
import modules.tui.src.surface_tui_main_action as surface_tui_main_action
import modules.tui.src.surface_tui_navlog_action as surface_tui_navlog_action
import modules.tui.src.surface_tui_sessions_action as surface_tui_sessions_action
import modules.tui.src.surface_tui_sessions_store as surface_tui_sessions_store
import modules.tui.src.surface_tui_settings_view as surface_tui_settings_view
import modules.tui.src.surface_tui_swarm_action as surface_tui_swarm_action
import modules.tui.src.surface_tui_utils_component as surface_tui_utils_component
import modules.tui.src.surface_tui_workers_store as surface_tui_workers_store

__all__ = [
    "surface_tui_app_screen",
    "surface_tui_component",
    "surface_tui_compose_layout",
    "surface_tui_css_view",
    "surface_tui_events_action",
    "surface_tui_sessions_action",
    "surface_tui_navlog_action",
    "surface_tui_chatlog_action",
    "surface_tui_swarm_action",
    "surface_tui_app_action",
    "surface_tui_main_action",
    "surface_tui_sessions_store",
    "surface_tui_settings_view",
    "surface_tui_utils_component",
    "surface_tui_workers_store",
]
