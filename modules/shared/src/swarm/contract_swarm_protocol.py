"""Swarm-domain capability contract (AES102 `_protocol`).

One file for the swarm feature, carrying one class per capability seam.
The swarm feature has three consumer-facing seams — start, progress,
cancel — plus the shared state store those three read through. Each seam
is sealed in its own protocol class and implemented by its own capability
file, so a test can inject a stub that only implements the seam it is
exercising.

``ISwarmRegistryProtocol`` is the shared bookkeeping behind the three
seams. It exists because capabilities never import one another: the start,
progress, and cancel capabilities are independent files, so the state they
have in common — snapshots, per-role cancel events, executors — is reached
through this one contract instead of through a sibling import. The root
container creates the single registry instance and injects it into all
three, so they observe one fan-out.

A single protocol file may declare many protocol classes: the count the
linter compares against the FR count is the class count, never the file
count.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping

from modules.shared.src.common.taxonomy_core_vo import CancelToken, FilePath, TaskExecutor
from modules.shared.src.swarm.taxonomy_swarm_vo import BrowserCount, SwarmId, SwarmSnapshot

__all__ = [
    "ISwarmStartProtocol",
    "ISwarmProgressProtocol",
    "ISwarmCancelProtocol",
    "ISwarmRegistryProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISwarmStartProtocol": "ISwarmStartProtocol",
    "ISwarmProgressProtocol": "ISwarmProgressProtocol",
    "ISwarmCancelProtocol": "ISwarmCancelProtocol",
    "ISwarmRegistryProtocol": "ISwarmRegistryProtocol",
}


class ISwarmStartProtocol(ABC):
    """Swarm start capability contract."""

    @property
    @abstractmethod
    def browser_concurrency(self) -> BrowserCount:
        """Configured browser concurrency for a single Swarm run."""
        ...

    @abstractmethod
    def start(self, input_path: FilePath, attachment_path: FilePath, headless: bool = True) -> SwarmSnapshot:
        """Start a fan-out over the discovered roles and return the initial snapshot.

        ``input_path`` is what the user pointed at — a file or a folder —
        and is recorded on the snapshot. ``attachment_path`` is the single
        material every role reads; the caller resolves a folder input down
        to it, because the fan-out threads read it on their first pass.

        ``headless`` decides whether each Chromium instance runs headless.
        ``True`` means no visible browser window; ``False`` shows the window.
        """
        ...


class ISwarmProgressProtocol(ABC):
    """Swarm progress capability contract."""

    @abstractmethod
    def snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when absent."""
        ...


class ISwarmCancelProtocol(ABC):
    """Swarm cancel capability contract."""

    @abstractmethod
    def cancel(self, swarm_id: SwarmId) -> None:
        """Cancel queued and active work for a swarm."""
        ...


class ISwarmRegistryProtocol(ABC):
    """Shared fan-out state store contract.

    Implemented by ``capabilities_swarm_registry.SwarmRegistry`` and
    injected into the start, progress, and cancel capabilities by the root
    container, so all three observe one fan-out without importing each
    other. Every mutation is applied under one lock and every accepted
    snapshot is persisted to ``manifest.json`` before the call returns, so
    a reader that sees a state change can always read the same state from
    disk.

    The registry owns bookkeeping only — no retry policy, no status rules.
    Those stay in the seam that decides them.
    """

    @abstractmethod
    def open_run(
        self,
        snapshot: SwarmSnapshot,
        cancel_events: Mapping[str, CancelToken],
        attachment: FilePath,
    ) -> None:
        """Register a new run with its cancel events and attachment, then persist it.

        ``cancel_events`` is keyed by role; ``attachment`` is the single
        material every leg of the run reads.
        """
        ...

    @abstractmethod
    def get_snapshot(self, swarm_id: SwarmId) -> SwarmSnapshot | None:
        """Return the latest snapshot for a swarm, or None when it is unknown."""
        ...

    @abstractmethod
    def revise(
        self, swarm_id: SwarmId, transform: Callable[[SwarmSnapshot], SwarmSnapshot | None]
    ) -> SwarmSnapshot | None:
        """Replace a stored snapshot with ``transform`` applied, under the registry lock.

        Returning None from ``transform`` keeps the stored snapshot as it
        is. Returns the stored snapshot after the call, or None when the
        swarm is unknown. The revised snapshot is persisted before this
        returns.
        """
        ...

    @abstractmethod
    def cancel_events(self, swarm_id: SwarmId) -> Mapping[str, CancelToken]:
        """Return the per-role cancel events of a swarm, empty when unknown."""
        ...

    @abstractmethod
    def attachment(self, swarm_id: SwarmId) -> FilePath | None:
        """Return the attachment every leg of a swarm reads, or None when unknown."""
        ...

    @abstractmethod
    def attach_executor(self, swarm_id: SwarmId, executor: TaskExecutor) -> None:
        """Bind the executor that runs the legs of a swarm."""
        ...

    @abstractmethod
    def release(self, swarm_id: SwarmId) -> TaskExecutor | None:
        """Drop a swarm's executor, cancel events, and attachment path.

        The snapshot itself is kept so a caller can still read the
        terminal state of a cancelled run. Returns the executor that was
        bound, or None when nothing was.
        """
        ...
