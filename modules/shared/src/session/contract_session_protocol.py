"""Session-domain capability contracts (AES102 `_protocol`).

One file for the session feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``ISessionManagerProtocol``       → ``SessionManager``        (pool CRUD, status marking)
- ``ISessionHealthCheckerProtocol`` → ``SessionHealthChecker``  (async ping, bulk health)
- ``ISessionRotatorProtocol``       → ``SessionRotationAdapter`` (round-robin selection)
- ``ISessionRenewalProtocol``       → ``SessionRenewer``        (token renewal, self-heal)

The outward export surface for outer layers is ``ISessionAggregate``
(validate/delete) in ``contract_session_aggregate.py``. Rotation has no
aggregate: the consumer that picks the next session calls
``ISessionRotatorProtocol`` on the capability directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.session.taxonomy_session_vo import (
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
    def get_session_by_name(self, name: SessionName) -> SessionInfo | None:
        """Return the pool entry registered under *name*, or None when absent."""
        ...

    @abstractmethod
    def remove_session_by_name(self, name: SessionName) -> bool:
        """Remove the pool entry registered under *name*; True when found."""
        ...

    @abstractmethod
    def delete_session_profile(self, profile_path: Path, *, force: bool = False) -> None:
        """Remove the saved Chromium profile directory at *profile_path*.

        The target must be an existing directory that clears every rule in
        ``is_safe_session_target``, and deletion is refused while no backup
        generation is retained unless *force* is set. Raise ``QwenCliError``
        when a partial removal leaves residue behind.
        """
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


class ISessionRenewalProtocol(ABC):
    """Session renewal contract: detect a stale auth session and renew it.

    Implemented by ``capabilities_session_renewal.SessionRenewer``. The
    caller invokes :meth:`renew_session_if_stale` before driving a chat
    prompt so an expired ``auth-session`` cookie can be transparently
    exchanged via the site's own refresh-token flow, without forcing the
    user back to ``qwa session login``.
    """

    @abstractmethod
    def renew_session_if_stale(
        self,
        cfg: AppConfig,
        *,
        session_path: Path | None = None,
    ) -> bool:
        """Renew the session credentials if the auth session is stale.

        Returns True when the session is healthy (either already, or after
        a successful renewal attempt). Raises ``AuthRequiredError`` when
        renewal is impossible or fails — the caller must fall back to
        manual login.

        :param cfg: Application configuration carrying the session profile
            path and headless flag.
        :param session_path: Optional explicit profile path override; when
            None the profile path is taken from ``cfg.session_path``.

        :raises AuthRequiredError: When the refresh token is dead or the
            browser warm-up cannot restore a valid session.
        """
        ...


__all__ = [
    "ISessionManagerProtocol",
    "ISessionHealthCheckerProtocol",
    "ISessionRotatorProtocol",
    "ISessionRenewalProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISessionManagerProtocol": ISessionManagerProtocol,
    "ISessionHealthCheckerProtocol": ISessionHealthCheckerProtocol,
    "ISessionRotatorProtocol": ISessionRotatorProtocol,
    "ISessionRenewalProtocol": ISessionRenewalProtocol,
}
