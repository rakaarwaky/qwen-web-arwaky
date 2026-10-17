"""CLI surface: init command — initialize workspace (.agents/skills + .qwen-web-arwaky).

Smart surface: delegates to the config aggregate, zero business logic.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.common.utility_response_normalizer import safe_handle, success_response
from modules.shared.src.config.contract_config_aggregate import IConfigAggregate
from modules.shared.src.config.taxonomy_config_vo import ConfigRequest, ConfigResponse


@safe_handle
def handle(args: object, config: IConfigAggregate) -> dict[str, object]:
    """Initialize the workspace in the target directory."""
    target_dir = Path(str(getattr(args, "target_dir", None) or Path.cwd()))
    response: ConfigResponse = config.execute(ConfigRequest(verb="init_workspace", input_path=target_dir))
    if response.error is not None:
        raise RuntimeError(response.error)
    return success_response(f"Workspace initialized in {target_dir}")


__all__ = ["handle"]
