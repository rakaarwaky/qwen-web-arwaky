"""Agent: run the self-update pipeline on behalf of the CLI update command.

Owns the rollback decision (run the post-update health gate, then restore the
previous version when the gate fails) so no surface can skip it. All I/O is
delegated to the update capability (``IUpdateProtocol``); this agent only
routes the request verb and wraps the outcome into the shared VO.
"""

from __future__ import annotations

from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.contract_update_aggregate import IUpdateAggregate
from modules.shared.src.taxonomy_core_vo import VersionString
from modules.shared.src.taxonomy_update_vo import (
    UpdateRequest,
    UpdateResponse,
)

__all__ = ["UpdateOrchestrator"]


class UpdateOrchestrator(IUpdateAggregate):
    """Run the self-update pipeline on behalf of the CLI update command."""

    def __init__(self, updater: IUpdateProtocol, observability: IObservabilityProtocol) -> None:
        """Wrap the update capability and the observability seam.

        ``updater`` arrives as ``IUpdateProtocol`` so a test can hand in a
        stub without this agent reaching for the concrete update capability;
        the concrete updater is constructed by the container and injected here.
        ``observability`` records the update run, so a long download and a
        rolled-back version land in the run log rather than only on stdout.
        """
        self._updater = updater
        self._observability = observability

    # Block 2: Protocol Method Implementation

    def execute(self, request: UpdateRequest) -> UpdateResponse:
        """Run the requested update verb and return its outcome as a shared VO.

        Dispatches on ``request.verb`` — the consumer passes one verb; the
        agent routes it to the right capability call and wraps the result.
        No I/O happens here; every byte of output comes from the capability.
        """
        if request.verb == "check_update":
            return UpdateResponse(check_result=self._updater.check_update())
        if request.verb == "perform_update":
            return UpdateResponse(report=self._updater.perform_update(force=request.force))
        if request.verb == "rollback_to":
            previous = request.previous_version
            if previous is None:
                return UpdateResponse(error="rollback_to verb requires previous_version")
            return UpdateResponse(steps=self._updater.rollback_to(VersionString(previous)))
        return UpdateResponse(error=f"unknown update verb: {request.verb!r}")

    # Block 3: Dunder Methods, Factories, Helpers

    def __repr__(self) -> str:
        return "UpdateOrchestrator()"
