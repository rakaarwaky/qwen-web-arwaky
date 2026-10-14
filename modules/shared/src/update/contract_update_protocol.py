"""Update-domain capability contracts (AES102 `_protocol`).

One file for the update feature. Four FR protocol classes, one per
functional requirement in ``modules/update/FRD.md``:

- ``IUpdateCheckProtocol``    → FR-UPDATE-001  (version discovery, no mutation)
- ``IUpdateUpgradeProtocol``  → FR-UPDATE-002  (package upgrade + browser sync)
- ``IUpdateVerifyProtocol``   → FR-UPDATE-003  (full pipeline + post-update gate)
- ``IUpdateRollbackProtocol`` → FR-UPDATE-004  (reverse-ordered restore)

The agent (``UpdateOrchestrator``) composes the four protocols and routes
verbs across the FRs.  The aggregate (``IUpdateAggregate``) is the single
entry point.  No umbrella composition class lives in this file: the
composition/routing job belongs to the aggregate and the agent, not to the
protocol file.

``ISmokeGate`` is the callable the Root layer injects for the FR-UPDATE-003
post-update functional health gate (issue #294 / #506).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeAlias

from modules.shared.src.common.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)


class IUpdateCheckProtocol(ABC):
    """FR-UPDATE-001: report the installed version and check for updates.

    Read-only: ``check_update`` must never mutate the environment.
    """

    @abstractmethod
    def current_version(self) -> VersionString:
        """Return the installed package version ('unknown' when unresolvable)."""

    @abstractmethod
    def check_update(self) -> UpdateCheckResult:
        """Compare the installed version against the latest published release."""


class IUpdateUpgradeProtocol(ABC):
    """FR-UPDATE-002: upgrade the package and synchronise the browser.

    The browser sync runs only after the package upgrade succeeds.
    """

    @abstractmethod
    def upgrade_package(
        self,
        force: ForceFlag = ForceFlag(False),
        *,
        target_version: str | None = None,
    ) -> UpdateStepResult:
        """Upgrade (or reinstall, when forced) the package via pip."""

    @abstractmethod
    def sync_browser(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Synchronise Playwright Chromium browser binaries.

        When forced, cached Chromium builds are purged before re-downloading.
        """


class IUpdateVerifyProtocol(ABC):
    """FR-UPDATE-003: run the full pipeline and verify the post-update state."""

    @abstractmethod
    def perform_update(self, force: ForceFlag = ForceFlag(False)) -> UpdateReport:
        """Run the full update pipeline and return the aggregated report.

        Sequence: version check → package upgrade → browser sync → health
        checks → functional smoke gate.  Every step is recorded in the report.
        """


class IUpdateRollbackProtocol(ABC):
    """FR-UPDATE-004: restore the previous release in reverse order.

    Rollback runs only after a FR-UPDATE-003 health-gate failure; it restores
    the package before the browser build and reconciles the dependency snapshot.
    """

    @abstractmethod
    def rollback_to(self, previous_version: VersionString) -> tuple[UpdateStepResult, ...]:
        """Rollback to a previously installed package version."""


#: Post-update functional health gate: a callable returning ``(name, passed, detail)`` triples.
#: The Root layer injects it so the update pipeline re-runs the doctor checks at
#: gate-execution time rather than at container-construction time (issue #294 / #506).
ISmokeGate: TypeAlias = Callable[[], tuple[tuple[str, bool, str], ...]]


__all__ = [
    "IUpdateCheckProtocol",
    "IUpdateUpgradeProtocol",
    "IUpdateVerifyProtocol",
    "IUpdateRollbackProtocol",
    "ISmokeGate",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IUpdateCheckProtocol": IUpdateCheckProtocol,
    "IUpdateUpgradeProtocol": IUpdateUpgradeProtocol,
    "IUpdateVerifyProtocol": IUpdateVerifyProtocol,
    "IUpdateRollbackProtocol": IUpdateRollbackProtocol,
    "ISmokeGate": ISmokeGate,
}
