"""qwen-web CLI surface — commands and controllers.

Barrel re-export of the CLI surfaces so the entry point reaches every command
module through one import. Each surface keeps its own name in this module's
namespace, which is what ``root_cli_main_entry`` dispatches to.
"""

import modules.cli.src.surface_cli_init_command as surface_cli_init_command
import modules.cli.src.surface_cli_interactive_controller as surface_cli_interactive_controller
import modules.cli.src.surface_cli_login_command as surface_cli_login_command
import modules.cli.src.surface_cli_run_command as surface_cli_run_command
import modules.cli.src.surface_cli_sessions_command as surface_cli_sessions_command
import modules.cli.src.surface_cli_update_command as surface_cli_update_command

__all__ = [
    "surface_cli_init_command",
    "surface_cli_interactive_controller",
    "surface_cli_login_command",
    "surface_cli_run_command",
    "surface_cli_sessions_command",
    "surface_cli_update_command",
]
