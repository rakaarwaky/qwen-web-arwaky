"""Config health probe capability — smoke gate for the update pipeline (AES403).

Implements ISmokeGate. Provides the functional doctor gate that the Root layer
injects for the FR-UPDATE-003 smoke verification. The gate is a callable returning
tuples of (name, passed, detail) describing each check, so the update pipeline
depends only on an injected callable, never on a Surface.

AES403: capability layer. Imports taxonomy, contract, and utility only.
"""

from __future__ import annotations

from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.update.contract_update_protocol import ISmokeGate


# Block 1: Class Definition & Constructor
class ConfigHealthProbeCapability(ISmokeGate):
    """Implements ISmokeGate via the functional doctor checks.

    Wire-up:
        session: ISessionAggregate

    Public method:
        __call__() -> tuple[tuple[str, bool, str], ...]
    """

    def __init__(self, session: ISessionAggregate) -> None:
        self._session = session

    def __call__(self) -> tuple[tuple[str, bool, str], ...]:
        """Run the smoke gate checks via the functional doctor form.

        Returns the same triples as the CLI doctor surface: (name, passed, detail)
        for every diagnostic check, so the update pipeline can iterate without
        parsing JSON or knowing about the underlying CLI surface.
        """
        from modules.cli.src.surface_cli_doctor_command import run_doctor_checks

        checks = run_doctor_checks(
            include_heavy=False,
            smoke=True,
            session=self._session,
        )
        return tuple(
            (str(check["name"]), bool(check["passed"]), str(check["detail"]))
            for check in checks
        )


# Block 2: Protocol Method Implementation

# Empty Block 2: no direct protocol trait implementation beyond the class

# Block 3: Dunder Methods, Factories & Helpers

__all__ = ["build_config_smoke_gate", "ConfigHealthProbeCapability"]