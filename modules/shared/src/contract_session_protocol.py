"""Session-domain capability contracts (AES102 `_protocol`).

One file for the session feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``ISessionManagerProtocol``       → ``SessionManager``        (pool CRUD, status marking)
- ``ISessionHealthCheckerProtocol`` → ``SessionHealthChecker``  (async ping, bulk health)
- ``ISessionRotatorProtocol``       → ``SessionRotationAdapter`` (round-robin selection)
- ``IRunCancelProtocol``            → ``RunCancelRegistry``      (targeted browser-context cancel)
- ``IWorkspaceProtocol``            → ``WorkspaceProvisioner`` (XDG dirs, symlinks, SKILL.md)

The outward export surface for outer layers is ``ISessionAggregate``
(validate/delete) in ``contract_session_aggregate.py``. Rotation has no
aggregate: the consumer that picks the next session calls
``ISessionRotatorProtocol`` on the capability directly.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from modules.shared.src.taxonomy_core_vo import FilePath, RunId, RunState
from modules.shared.src.taxonomy_session_vo import (
    RotatorRequest,
    RotatorResponse,
    SessionId,
    SessionInfo,
    SessionList,
    SessionName,
    SessionPool,
)


class ISessionManagerProtocol(ABC):
    """Session storage, CRUD, and status-marking contract."""

    @abstractmethod
    def load_pool(self) -> SessionPool:
        """Load the session pool from disk, or an empty pool when absent."""
        ...

    @abstractmethod
    def save_pool(self, pool: SessionPool) -> None:
        """Persist the session pool to disk."""
        ...

    @abstractmethod
    def add_session(self, name: SessionName, profile_path: Path) -> SessionInfo:
        """Create and persist a new session; return the stored metadata."""
        ...

    @abstractmethod
    def remove_session(self, session_id: SessionId) -> bool:
        """Remove the session by *session_id*; True when one was removed."""
        ...

    @abstractmethod
    def list_sessions(self) -> SessionList:
        """Return every session in the pool."""
        ...

    @abstractmethod
    def get_session(self, session_id: SessionId) -> SessionInfo | None:
        """Return the session by *session_id*, or None when absent."""
        ...

    @abstractmethod
    def get_next_healthy_session(self) -> SessionInfo | None:
        """Return the next healthy session for rotation, or None when all are limited."""
        ...

    @abstractmethod
    def mark_limited(self, session_id: SessionId) -> None:
        """Mark the session as rate-limited."""
        ...

    @abstractmethod
    def mark_healthy(self, session_id: SessionId) -> None:
        """Mark the session as healthy."""
        ...


class ISessionHealthCheckerProtocol(ABC):
    """Async session health-check contract (ping test per session)."""

    @abstractmethod
    async def check_session(self, session: SessionInfo) -> bool:
        """Return True when *session* is healthy, False when rate-limited."""
        ...

    @abstractmethod
    async def check_all_sessions(self, pool: SessionPool) -> SessionPool:
        """Health-check every session and return the updated pool."""
        ...


class ISessionRotatorProtocol(ABC):
    """Session rotation contract: select the next healthy session to use."""

    @abstractmethod
    async def rotate(self, request: RotatorRequest) -> RotatorResponse:
        """Select the next healthy session from the pool and return it.

        A coroutine because selecting a session awaits the health ping that
        proves the pooled session is still usable.
        """
        ...

    @abstractmethod
    async def get_next_session(self) -> SessionInfo | None:
        """Pick the next healthy session by round-robin order.

        Returns None once every pooled session is rate-limited.
        """
        ...


class IRunCancelProtocol(ABC):
    """Contract for the shared targeted-cancel registry of in-flight runs.

    Implemented by ``capabilities_run_cancel_registry.CapabilitiesRunCancelRegistry``
    and injected into the prompt file / attachment / swarm orchestrators so
    that a cancel can stop one run's browser context without touching sibling
    runs.  Runs are addressed by their stable ``RunId`` — never by object
    identity of a ``threading.Event`` — so the handle cannot be invalidated
    by a collected or recycled event object.
    """

    @abstractmethod
    def register(self, run_state: RunState) -> None:
        """Track a newly started in-flight run."""
        ...

    @abstractmethod
    def release(self, run_state: RunState) -> None:
        """Drop the entry for a finished run."""
        ...

    @abstractmethod
    def cancel_run(self, run_id: RunId) -> None:
        """Stop the run identified by ``run_id`` and close its browser context."""
        ...

    @abstractmethod
    def cancel_by_event(self, cancel_event: threading.Event) -> None:
        """Cancel the run that was registered with this cancel event.

        Convenience for surface callers that only hold the original
        ``threading.Event``.  Delegates to the stable ``run_id`` lookup
        internally; safe no-op when the run has already finished.
        """
        ...

    @abstractmethod
    def set_active_bctx(self, run_id: RunId, bctx: Any) -> None:
        """Update the live browser context for a registered run (None clears it)."""
        ...

    @abstractmethod
    def active_bctx(self, run_id: RunId) -> Any:
        """Return the live browser context for ``run_id``, or None."""
        ...


class IWorkspaceProtocol(ABC):
    """Workspace directory provisioning contract."""

    @abstractmethod
    def init_workspace(self, target_dir: FilePath) -> None:
        """Initialize XDG directories, SKILL.md, .qwen-web symlinks, and .gitignore."""
        ...


__all__ = [
    "ISessionManagerProtocol",
    "ISessionHealthCheckerProtocol",
    "ISessionRotatorProtocol",
    "IRunCancelProtocol",
    "IWorkspaceProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISessionManagerProtocol": ISessionManagerProtocol,
    "ISessionHealthCheckerProtocol": ISessionHealthCheckerProtocol,
    "ISessionRotatorProtocol": ISessionRotatorProtocol,
    "IRunCancelProtocol": IRunCancelProtocol,
    "IWorkspaceProtocol": IWorkspaceProtocol,
}
