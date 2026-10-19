"""qwen-web-arwaky CLI surface — commands and controllers.

Barrel re-export of all ten CLI surfaces so the entry point reaches every
command module through one import. Each surface keeps its own name in this
module's namespace, which is what ``root_cli_main_entry`` dispatches to.
"""

import modules.cli.src.surface_cli_doctor_command as surface_cli_doctor_command
import modules.cli.src.surface_cli_init_command as surface_cli_init_command
import modules.cli.src.surface_cli_interactive_controller as surface_cli_interactive_controller
import modules.cli.src.surface_cli_jobs_command as surface_cli_jobs_command
import modules.cli.src.surface_cli_json_hook as surface_cli_json_hook
import modules.cli.src.surface_cli_observability_command as surface_cli_observability_command
import modules.cli.src.surface_cli_run_command as surface_cli_run_command
import modules.cli.src.surface_cli_sessions_command as surface_cli_sessions_command
import modules.cli.src.surface_cli_swarm_command as surface_cli_swarm_command
import modules.cli.src.surface_cli_update_command as surface_cli_update_command

__all__ = [
    "surface_cli_doctor_command",
    "surface_cli_init_command",
    "surface_cli_interactive_controller",
    "surface_cli_jobs_command",
    "surface_cli_observability_command",
    "surface_cli_json_hook",
    "surface_cli_run_command",
    "surface_cli_sessions_command",
    "surface_cli_swarm_command",
    "surface_cli_update_command",
]
