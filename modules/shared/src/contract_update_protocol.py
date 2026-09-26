"""Update-domain capability contract (AES102 `_protocol`).

One file for the update feature. The update feature has one capability
seam, ``IUpdateProtocol``: it carries every method ``UpdateManager``
implements, with one concrete return type each, so the capability
implements its class outright and never carries stubs.

``IUpdateAggregate`` in ``contract_update_aggregate.py`` is the outward
export surface for outer layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    RollbackSteps,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)


class IUpdateProtocol(ABC):
    """Self-update and environment-synchronisation capability contract.

    Owns the full update pipeline: remote version discovery via the
    GitHub Releases API, package upgrade via git pull / pip (with PEP 610
    editable dev-repo detection), Playwright Chromium binary
    synchronisation, and post-update installation-integrity health checks.
    """

    @abstractmethod
    def current_version(self) -> VersionString:
        """Return the installed package version ('unknown' when unresolvable)."""
        ...

    @abstractmethod
    def check_update(self) -> UpdateCheckResult:
        """Compare the installed version against the latest published release.

        Read-only: must never mutate the environment.
        """
        ...

    @abstractmethod
    def upgrade_package(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Upgrade (or reinstall, when forced) the package via pip."""
        ...

    @abstractmethod
    def sync_browser(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Synchronise Playwright Chromium browser binaries.

        When forced, cached Chromium builds are purged before re-downloading.
        """
        ...

    @abstractmethod
    def perform_update(self, force: ForceFlag = ForceFlag(False)) -> UpdateReport:
        """Run the full update pipeline and return the aggregated report.

        Sequence: version check → package upgrade → browser sync → health checks.
        """
        ...

    @abstractmethod
    def rollback_to(self, previous_version: VersionString) -> RollbackSteps:
        """Rollback to a previously installed package version."""
        ...


__all__ = ["IUpdateProtocol"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IUpdateProtocol": IUpdateProtocol,
}
