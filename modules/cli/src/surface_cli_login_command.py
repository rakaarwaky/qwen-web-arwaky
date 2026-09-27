"""CLI surface for manual login/session setup."""

from __future__ import annotations

from modules.shared.src.contract_session_aggregate import ISessionAggregate
from modules.shared.src.contract_setup_aggregate import ISetupAggregate
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.taxonomy_setup_vo import SetupRequest
from modules.shared.src.utility_core_response import safe_handle, success_response


@safe_handle
def handle(
    _args: object,
    _session: ISessionAggregate,
    setup: ISetupAggregate,
    cfg: AppConfig,
) -> dict[str, object]:
    """Validate or establish a manual login session in a visible browser.

    The user logs in manually in the headed browser, then closes it — that
    triggers the session check. No ENTER press needed.
    """
    response = setup.execute(SetupRequest(profile_path=cfg.session_path))
    return success_response(response.error or response.message or response.profile_path or "")
