"""Config health probe capability — smoke gate for the update pipeline (AES403).

Implements ``IConfigHealthProbeProtocol`` (FR-UPDATE-003, issues #294 / #506).
The gate is the functional doctor form the Root layer injects into the update
pipeline: a callable returning ``(name, passed, detail)`` triples, so the
update capability depends only on an injected callable, never on a Surface.

AES403: capability layer. Imports taxonomy, contract, and utility only.
"""

from __future__ import annotations

from modules.shared.src.config.contract_config_protocol import IConfigHealthProbeProtocol
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate

# Block 1: Class Definition & Constructor


class ConfigHealthProbeCapability(IConfigHealthProbeProtocol):
    """Implements the smoke gate contract via the functional doctor checks.

    Wire-up:
        session: ISessionAggregate

    Public method:
        __call__() -> tuple[tuple[str, bool, str], ...]
    """

    def __init__(self, session: ISessionAggregate) -> None:
        self._session = session

    # Block 2: Protocol Method Implementation

    def __call__(self) -> tuple[tuple[str, bool, str], ...]:
        """Run the smoke gate checks via the functional doctor form.

        Returns the same triples the CLI doctor surface reports —
        (name, passed, detail) for every diagnostic check — so the update
        pipeline can iterate them without parsing JSON or knowing about the
        CLI surface.
        """
        from modules.cli.src.surface_cli_doctor_command import run_doctor_checks

        checks = run_doctor_checks(
            include_heavy=False,
            smoke=True,
            session=self._session,
        )
        return tuple((str(check["name"]), bool(check["passed"]), str(check["detail"])) for check in checks)

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        return f"ConfigHealthProbeCapability(session={self._session!r})"


def build_config_smoke_gate(session: ISessionAggregate) -> IConfigHealthProbeProtocol:
    """Factory that returns a smoke gate callable for the update pipeline.

    The Root layer injects this callable, never the class itself, to keep the
    wiring explicit. Callers get a simple callable that executes the same
    doctor checks the CLI surface reports, so the post-flight gate cannot
    disagree with the interactive ``qwen-web-arwaky doctor`` (issue #294).
    """
    return ConfigHealthProbeCapability(session)


__all__ = ["build_config_smoke_gate", "ConfigHealthProbeCapability"]
