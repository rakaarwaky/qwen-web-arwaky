"""CLI surface: init command — initialize workspace (.agents/skills + .qwen-web).

Smart surface: delegates to the workspace provisioner capability, zero business logic.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_vo import FilePath
from modules.shared.src.utility_response_normalizer import safe_handle, success_response


@safe_handle
def handle(args: object, workspace: IWorkspaceProtocol) -> dict[str, object]:
    """Initialize the workspace in the target directory."""
    target_dir = Path(str(getattr(args, "target_dir", None) or Path.cwd()))
    workspace.init_workspace(FilePath(target_dir))
    return success_response(f"Workspace initialized in {target_dir}")
