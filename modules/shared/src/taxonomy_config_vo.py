"""Taxonomy: config-feature value objects.

The config feature reports on itself in four shapes: a sandbox-mode
verdict, a list of configuration problems, a set of resolved paths, and
a host-capacity report. Each is a frozen value object so a caller can
hold the result, compare it, and print it without reaching back into
the capability that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NewType, TypeAlias

#: How a config finding should be surfaced. ``error`` blocks a run;
#: ``warning`` describes a working-but-undesirable state.
ConfigSeverity = Literal["error", "warning"]

#: Why the config produced a finding. Maps onto the operator runbook index
#: in ``utility_core_env`` so a message can name the doc that fixes it.
ConfigCategory = Literal["file_io", "response_timeout", "other"]

#: Which sandbox verdict the host supports.
SandboxState = Literal["sandboxed", "disabled_by_env", "disabled_by_host", "forced"]

SandboxVerdict: TypeAlias = str
ConfigIssueText: TypeAlias = str
ModelName: TypeAlias = str
ByteCount = NewType("ByteCount", int)
WorkerCount = NewType("WorkerCount", int)


@dataclass(frozen=True)
class SandboxReport:
    """The sandbox mode Chromium will actually launch under, and why.

    ``state`` is one of the ``SandboxState`` literals; ``reason`` is the
    operator-facing sentence naming the env switch or host limitation
    that decided it, so a diagnostic message needs no second lookup.
    """

    state: SandboxState
    reason: ConfigIssueText
    host_supports_sandbox: bool


@dataclass(frozen=True)
class ConfigIssue:
    """One configuration problem, shaped for display.

    A bare ``ValueError`` from ``AppConfig.validate`` names the field and
    stops there. An issue carries the severity, the category the operator
    runbook index keys on, and a sentence that says what to do about it.
    """

    field: str
    message: ConfigIssueText
    severity: ConfigSeverity = "error"
    category: ConfigCategory = "other"

    @property
    def blocks_run(self) -> bool:
        """True when this issue must stop a run rather than warn about it."""
        return self.severity == "error"


@dataclass(frozen=True)
class ConfigIssues:
    """Every problem found in one configuration, ready to print.

    ``errors`` and ``warnings`` are the two views a caller needs: a run
    command refuses on any error, while a diagnostic command reports both.
    """

    issues: tuple[ConfigIssue, ...] = ()

    @property
    def errors(self) -> tuple[ConfigIssue, ...]:
        """The subset that must block a run."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ConfigIssue, ...]:
        """The subset that describes a working-but-undesirable state."""
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        """True when nothing blocks a run."""
        return not self.errors

    def __bool__(self) -> bool:
        """False when any error is present, so ``if issues:`` reads naturally."""
        return bool(self.errors)


@dataclass(frozen=True)
class ResolvedConfigPath:
    """One config path, its role, and whether the host can use it.

    ``exists`` is false for a directory that has not been created yet,
    which is not a problem: ``writable`` is the field a caller acts on.
    """

    role: str
    path: Path
    exists: bool
    writable: bool


@dataclass(frozen=True)
class ResolvedConfigPaths:
    """Every path an ``AppConfig`` points at, with host access verified.

    ``issues`` carries every path problem found, so a diagnostic can
    show them all; ``ok`` answers the narrower question a run asks, which
    is whether any of them is severe enough to stop the run.
    """

    paths: tuple[ResolvedConfigPath, ...] = ()
    issues: tuple[ConfigIssue, ...] = ()

    @property
    def errors(self) -> tuple[ConfigIssue, ...]:
        """The subset that must block a run."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ConfigIssue, ...]:
        """The subset that describes a working-but-undesirable state."""
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        """True when no path problem blocks a run."""
        return not self.errors


@dataclass(frozen=True)
class CapacityReport:
    """What the host can carry, and where the effective worker count came from.

    ``effective_max_workers`` is the number the job executor will use.
    ``source`` names the derivation so an operator reading a diagnostic
    knows whether the host decided it or an env switch did.
    """

    total_memory: ByteCount
    available_memory: ByteCount
    recommended_max_workers: WorkerCount
    effective_max_workers: WorkerCount
    source: ConfigIssueText
    over_capacity: bool = False


__all__ = [
    "ByteCount",
    "CapacityReport",
    "ConfigCategory",
    "ConfigIssue",
    "ConfigIssueText",
    "ConfigIssues",
    "ConfigSeverity",
    "ModelName",
    "ResolvedConfigPath",
    "ResolvedConfigPaths",
    "SandboxReport",
    "SandboxState",
    "SandboxVerdict",
    "WorkerCount",
]
