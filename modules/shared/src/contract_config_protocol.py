"""Config-domain capability contract (AES102 `_protocol`).

Four capability seams back the config feature, each owning one kind of
self-inspection that the CLI surface used to perform inline:

- ``IConfigEnvironmentProtocol`` — what the host's environment resolves to
- ``IConfigValidatorProtocol``    — whether an ``AppConfig`` can run
- ``IConfigPathResolverProtocol`` — where the config's paths point and
  whether the host can write them
- ``IConfigCapacityProtocol``     — how many browsers the host can carry

``IConfigAggregate`` in ``contract_config_aggregate.py`` is the outward
export surface for outer layers: the CLI and the sibling orchestrators
call that one ``execute`` and never reach for a protocol here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_config_vo import (
    CapacityReport,
    ConfigIssues,
    ModelName,
    ResolvedConfigPaths,
    SandboxReport,
    WorkerCount,
)
from modules.shared.src.taxonomy_core_vo import AppConfig, TimeoutSec


class IConfigEnvironmentProtocol(ABC):
    """Resolve the operator's environment into the values config obeys.

    Every env-derived policy decision in the application lands here: the
    sandbox verdict, the response-wait ceiling, the worker and Swarm
    concurrency caps, and the pinned model. A caller asks this seam
    instead of reading ``os.environ`` so one probe governs the value the
    runtime uses and the value a diagnostic reports.
    """

    @abstractmethod
    def sandbox_report(self) -> SandboxReport:
        """Return the sandbox mode Chromium will launch under, and why.

        An explicit env switch outranks host detection, so a host that
        cannot provide a sandbox still reports the opt-in that forced
        the drop rather than the host limitation.
        """
        ...

    @abstractmethod
    def request_timeout_sec(self) -> TimeoutSec:
        """Return the response-wait ceiling in force, honouring the env override.

        An unparseable or non-positive override falls back to the built-in
        default instead of failing the pipeline boot.
        """
        ...

    @abstractmethod
    def max_workers(self) -> WorkerCount:
        """Return the job-executor worker count in force.

        The env override wins over the memory-derived recommendation, which
        is what lets an operator who knows their host raise the cap.
        """
        ...

    @abstractmethod
    def swarm_concurrency(self) -> WorkerCount:
        """Return the browser fan-out cap for one Swarm."""
        ...

    @abstractmethod
    def swarm_headless(self) -> bool:
        """Return whether Swarm browsers run headless."""
        ...

    @abstractmethod
    def model(self) -> ModelName:
        """Return the model pinned at chat start, or the empty string for the default."""
        ...


class IConfigValidatorProtocol(ABC):
    """Report whether an ``AppConfig`` can drive a run.

    ``AppConfig.validate`` raises on the first bad field, which tells a
    run command what broke but not what to change. This seam returns every
    problem as a displayable issue so a caller can list them all and name
    the remedy for each.
    """

    @abstractmethod
    def validate(self, app_config: AppConfig) -> ConfigIssues:
        """Return every problem found in *app_config*, empty when it can run."""
        ...


class IConfigPathResolverProtocol(ABC):
    """Resolve a config's paths and verify the host can use them.

    Output writability is checked here so a run refuses a destination it
    cannot write before spending browser time discovering it.
    """

    @abstractmethod
    def resolve_paths(self, app_config: AppConfig) -> ResolvedConfigPaths:
        """Return every path *app_config* names, with existence and writability verified.

        A path that is absent but whose parent is writable is not a problem:
        the output and log directories are created on demand.
        """
        ...


class IConfigCapacityProtocol(ABC):
    """Report the browser fan-out this host can carry.

    The limit is derived from available memory rather than a fixed
    constant, so the reported number matches what the job executor will
    actually use (issue #291).
    """

    @abstractmethod
    def report(self) -> CapacityReport:
        """Return measured capacity, the recommended limit, and the effective one.

        ``over_capacity`` is set when an env override raised the effective
        count above what the measured memory supports, which is the case
        an operator most needs to see.
        """
        ...


__all__ = [
    "IConfigCapacityProtocol",
    "IConfigEnvironmentProtocol",
    "IConfigPathResolverProtocol",
    "IConfigValidatorProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols: dict[str, object] = {
    "IConfigCapacityProtocol": IConfigCapacityProtocol,
    "IConfigEnvironmentProtocol": IConfigEnvironmentProtocol,
    "IConfigPathResolverProtocol": IConfigPathResolverProtocol,
    "IConfigValidatorProtocol": IConfigValidatorProtocol,
}
