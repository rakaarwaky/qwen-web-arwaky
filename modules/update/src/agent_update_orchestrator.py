"""Agent: run the self-update pipeline on behalf of the CLI update command.

Owns the rollback decision (run the post-update health gate, then restore the
previous version when the gate fails) so no surface can skip it. All I/O is
delegated to the four update capability protocols; this agent only routes
the request verb and wraps the outcome into the shared VO.
"""

from __future__ import annotations

from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.contract_update_aggregate import IUpdateAggregate
from modules.shared.src.contract_update_protocol import (
    IUpdateCheckProtocol,
    IUpdateRollbackProtocol,
    IUpdateUpgradeProtocol,
    IUpdateVerifyProtocol,
)
from modules.shared.src.taxonomy_core_vo import VersionString
from modules.shared.src.taxonomy_update_vo import (
    UpdateRequest,
    UpdateResponse,
)

__all__ = ["UpdateOrchestrator"]


class UpdateOrchestrator(IUpdateAggregate):
    """Run the self-update pipeline on behalf of the CLI update command."""

    def __init__(
        self,
        check: IUpdateCheckProtocol,
        upgrade: IUpdateUpgradeProtocol,
        verify: IUpdateVerifyProtocol,
        rollback: IUpdateRollbackProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        """Wrap the four update capability protocols and the observability seam.

        Each capability arrives as its protocol so a test can hand in a stub
        without this agent reaching for the concrete capabilities; the
        concrete capabilities are constructed by the container and injected here.
        ``observability`` records the update run, so a long download and a
        rolled-back version land in the run log rather than only on stdout.
        """
        self._check = check
        self._upgrade = upgrade
        self._verify = verify
        self._rollback = rollback
        self._observability = observability

    # Block 2: Protocol Method Implementation

    def execute(self, request: UpdateRequest) -> UpdateResponse:
        """Run the requested update verb and return its outcome as a shared VO.

        Dispatches on ``request.verb`` — the consumer passes one verb; the
        agent routes it to the right capability call and wraps the result.
        No I/O happens here; every byte of output comes from the capability.
        """
        if request.verb == "current_version":
            return UpdateResponse(version=self._check.current_version())
        if request.verb == "check_update":
            return UpdateResponse(check_result=self._check.check_update())
        if request.verb == "upgrade_package":
            return UpdateResponse(step_result=self._upgrade.upgrade_package(force=request.force))
        if request.verb == "sync_browser":
            return UpdateResponse(step_result=self._upgrade.sync_browser(force=request.force))
        if request.verb == "perform_update":
            return UpdateResponse(report=self._verify.perform_update(force=request.force))
        if request.verb == "rollback_to":
            previous = request.previous_version
            if previous is None:
                return UpdateResponse(error="rollback_to verb requires previous_version")
            return UpdateResponse(steps=self._rollback.rollback_to(VersionString(previous)))
        # Untrusted callers (MCP) may pass any string; refuse it by name.
        return UpdateResponse(error=f"unknown update verb: {request.verb!r}")

    # Block 3: Dunder Methods, Factories, Helpers

    def __repr__(self) -> str:
        return "UpdateOrchestrator()"
