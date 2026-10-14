"""CLI surface: init command — initialize workspace (.agents/skills + .qwen-web-arwaky).

Smart surface: delegates to the workspace provisioner capability, zero business logic.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.common.taxonomy_core_vo import FilePath
from modules.shared.src.common.utility_response_normalizer import safe_handle, success_response
from modules.shared.src.config.contract_config_protocol import IWorkspaceProtocol


@safe_handle
def handle(args: object, workspace: IWorkspaceProtocol) -> dict[str, object]:
    """Initialize the workspace in the target directory."""
    target_dir = Path(str(getattr(args, "target_dir", None) or Path.cwd()))
    workspace.init_workspace(FilePath(target_dir))
    return success_response(f"Workspace initialized in {target_dir}")
