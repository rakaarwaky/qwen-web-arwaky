"""Config health probe capability — smoke gate for the update pipeline (AES403).

Implements ISmokeGate. Provides the functional doctor gate that the Root layer
injects for the FR-UPDATE-003 smoke verification. The gate is a callable returning
tuples of (name, passed, detail) describing each check, so the update pipeline
depends only on an injected callable, never on a Surface.
"""

from __future__ import annotations

from typing import cast

from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.update.contract_update_protocol import ISmokeGate


def build_config_smoke_gate(session: ISessionAggregate) -> ISmokeGate:
    """Create the smoke gate callable for the update pipeline.

    The smoke gate delegates to the functional ``doctor`` form, reusing the
    ``ISessionAggregate`` so that ``doctor`` and the smoke gate share the same
    session pool state (issue #294). ``run_doctor_checks`` is imported from the
    CLI surface module so the checks stay co-located and DRY.

    Parameters
    ----------
    session: ISessionAggregate
        The injected session aggregate providing the pool; necessary for
        ``doctor`` because the smoke gate needs a session to validate.

    Returns
    -------
    ISmokeGate
        Callable returning ``(name, passed, detail)`` triples for each check.
    """
    from modules.cli.src.surface_cli_doctor_command import run_doctor_checks

    def _gate() -> tuple[tuple[str, bool, str], ...]:
        checks = run_doctor_checks(
            include_heavy=False,
            smoke=True,
            session=session,
        )
        return tuple(
            (str(check["name"]), bool(check["passed"]), str(check["detail"]))
            for check in checks
        )

    return _gate


__all__ = ["build_config_smoke_gate"]