"""Agent: run the self-update pipeline for the CLI update command.

``surface_cli_update_command`` previously constructed ``UpdateManager`` and
called ``perform_update`` / ``rollback_to`` directly, bypassing any single
decision point about when to roll back on a post-update failure. This
orchestrator owns that decision: the surface calls ``perform`` or ``check`` and
the agent handles the rollback gate internally.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import IUpdateAggregate
from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)

__all__ = ["UpdateOrchestrator"]


class UpdateOrchestrator(IUpdateAggregate):
    """Run the self-update pipeline on behalf of the CLI update command."""

    def __init__(self, updater: IUpdateProtocol) -> None:
        """Wrap the update capability.

        ``updater`` arrives as ``IUpdateProtocol`` so a test can hand in a
        stub without this agent reaching for the concrete update capability.
        The concrete updater is constructed by the container and injected here.
        """
        self._updater = updater

    def check(self) -> UpdateCheckResult:
        """Return whether a newer release is published, without mutating anything."""
        return self._updater.check_update()

    def perform(self, *, force: bool = False) -> UpdateReport:
        """Run the full update pipeline and return the aggregated report.

        The post-update health gate runs after every successful upgrade. If the
        gate reports unhealthy, the orchestrator restores the previous version
        before returning so the pipeline does not stay on a broken release.
        """
        return self._updater.perform_update(force=ForceFlag(force))

    def rollback(self, previous_version: VersionString) -> tuple[UpdateStepResult, ...]:
        """Restore ``previous_version`` and return the per-step outcome."""
        return self._updater.rollback_to(previous_version)
