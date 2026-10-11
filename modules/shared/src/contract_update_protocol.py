"""Update-domain capability contracts (AES102 `_protocol`).

One file for the update feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IUpdateProtocol`` → ``UpdateManager`` (version discovery, package
  upgrade, Chromium sync, health checks, rollback)

The post-update functional health gate (``ISmokeGate``) is a callable
alias the Root layer injects so the update pipeline re-runs the doctor
checks at gate-execution time rather than at container-construction time.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeAlias

from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)


class IUpdateProtocol(ABC):
    """Self-update & environment synchronization capability contract.

    Owns the full update pipeline: remote version discovery via GitHub Releases API,
    package upgrade via git pull / pip (with PEP 610 editable dev-repo detection),
    Playwright Chromium binary synchronization, and post-update installation-integrity
    health checks.
    """

    @abstractmethod
    def current_version(self) -> VersionString:
        """Return the installed package version ('unknown' when unresolvable)."""

    @abstractmethod
    def check_update(self) -> UpdateCheckResult:
        """Compare the installed version against the latest published release.

        Read-only: must never mutate the environment.
        """

    @abstractmethod
    def upgrade_package(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Upgrade (or reinstall, when forced) the package via pip."""

    @abstractmethod
    def sync_browser(self, force: ForceFlag = ForceFlag(False)) -> UpdateStepResult:
        """Synchronize Playwright Chromium browser binaries.

        When forced, cached Chromium builds are purged before re-downloading.
        """

    @abstractmethod
    def perform_update(self, force: ForceFlag = ForceFlag(False)) -> UpdateReport:
        """Run the full update pipeline and return the aggregated report.

        Sequence: version check → package upgrade → browser sync → health checks.
        """

    @abstractmethod
    def rollback_to(self, previous_version: VersionString) -> tuple[UpdateStepResult, ...]:
        """Rollback to a previously installed package version."""


#: Post-update functional health gate: a callable returning ``(name, passed, detail)`` triples.
#: The Root layer injects it so the update pipeline re-runs the doctor checks at
#: gate-execution time rather than at container-construction time (issue #506).
ISmokeGate: TypeAlias = Callable[[], tuple[tuple[str, bool, str], ...]]


__all__ = [
    "IUpdateProtocol",
    "ISmokeGate",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IUpdateProtocol": IUpdateProtocol,
    "ISmokeGate": ISmokeGate,
}
