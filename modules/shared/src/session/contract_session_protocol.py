"""Session-domain capability contracts (AES102 `_protocol`).

One file for the session feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``ISessionManagerProtocol``       → ``SessionManager``        (pool CRUD, status marking)
- ``ISessionLoginCheckerProtocol``  → ``SessionLoginChecker``   (is the Qwen page authenticated?)
- ``ISessionLimitCheckerProtocol``  → ``SessionLimitChecker``   (is the Qwen page rate-limited?)
- ``ISessionRotatorProtocol``       → ``SessionRotator``         (round-robin selection)
- ``ISessionRenewalProtocol``       → ``SessionRenewer``        (token renewal, self-heal)

The outward export surface for outer layers is ``ISessionAggregate``
(validate/delete) in ``contract_session_aggregate.py``. Rotation has no
aggregate: the consumer that picks the next session calls
``ISessionRotatorProtocol`` on the capability directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path

from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.session.taxonomy_session_vo import (
    RotatorRequest,
    RotatorResponse,
    SessionHealthResult,
    SessionId,
    SessionInfo,
    SessionList,
    SessionName,
    SessionPool,
    SessionReason,
)


class IProfilePreparerProtocol(ABC):
    """Session profile preparation — mode→clone decision for browser profiles.

    Owns the ephemeral profile clone decision and hands the browser layer a
    plain prepared Path. The browser capability never clones the profile
    itself (AES201).
    """

    @abstractmethod
    def prepare(self, cfg: AppConfig) -> AbstractContextManager[Path]:
        """Return a context manager that yields a prepared session profile path.

        For login mode, yields the master session path directly.
        For standard modes, clones the master into an ephemeral temp dir
        and yields the clone path (cleaned up on exit).
        """
        ...


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
    def delete_session_profile(self, profile_path: Path, *, force: bool = False) -> bool:
        """Remove the saved Chromium profile directory at *profile_path*.

        The target must be an existing directory that clears every rule in
        ``is_safe_session_target``, and deletion is refused while no backup
        generation is retained unless *force* is set. Raise ``QwenCliError``
        when a partial removal leaves residue behind. Returns True when the
        profile was removed, False when the target did not exist.
        """
        ...

    @abstractmethod
    def find_pool_profile_with_content(self) -> Path | None:
        """Return the first pool session path holding real Chromium content.

        Pool entries are registered metadata, not a guarantee the profile
        directory still exists: a session can be registered while its
        ``Local State`` / ``Default/Cookies`` files were removed. Scanning
        the pool for the first entry whose path is a directory with either
        marker file is filesystem I/O that belongs to the storage
        capability, not to an agent. Returns ``None`` when the pool has no
        on-disk profile.
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
    def mark_limited(self, session_id: SessionId, reason: SessionReason | None = None) -> None:
        """Mark the session as rate-limited, with the sub-cause reason.

        ``SessionPool.mark_limited`` persists ``None`` unchanged, but the
        capability implementation defaults to ``"QUOTA"`` and
        ``SessionInfo`` readers treat a missing reason as ``"QUOTA"``, so
        implementors that pass ``None`` still surface a quota reason on
        read.
        """
        ...

    @abstractmethod
    def mark_healthy(self, session_id: SessionId) -> None:
        """Mark the session as healthy."""
        ...

    @abstractmethod
    def mark_auth_required(self, session_id: SessionId, reason: SessionReason | None = None) -> None:
        """Mark the session as requiring re-authentication or setup."""
        ...

    @abstractmethod
    def mark_used(self, session_id: SessionId, *, success: bool = True) -> None:
        """Record a completed request against the session under the pool lock."""
        ...


class ISessionLoginCheckerProtocol(ABC):
    """Login-session check contract.

    Answers one question: does the Qwen chat page behind *session* still
    carry an authenticated account?

    - ``ACTIVE``       — the page shows the authenticated chat UI and a live composer.
    - ``AUTH_REQUIRED`` — the page is a login/guest/expired view or the probe could not
      open an authenticated page.

    A rate-limited page that is still signed in is not a login failure, so the
    checker never reports ``LIMITED``: limit detection is the
    :class:`ISessionLimitCheckerProtocol` concern.
    """

    @abstractmethod
    async def check_session(self, session: SessionInfo) -> SessionHealthResult:
        """Probe *session* and return the login verdict (ACTIVE or AUTH_REQUIRED)."""
        ...


class ISessionLimitCheckerProtocol(ABC):
    """Rate-limit check contract.

    Answers one question: does the Qwen chat page behind *session* still
    reply, or is it rate-limited?

    - ``ACTIVE``  — the page is healthy and not rate-limited.
    - ``LIMITED`` — the page shows a provider limit banner, or the probe
      timed out / could not get a reply (treated as a limit signal).

    An expired session is not a limit, so the checker never reports
    ``AUTH_REQUIRED``: login detection is the
    :class:`ISessionLoginCheckerProtocol` concern.
    """

    @abstractmethod
    async def check_session(self, session: SessionInfo) -> SessionHealthResult:
        """Probe *session* and return the limit verdict (ACTIVE or LIMITED)."""
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

    @abstractmethod
    def rotate_sync(self, request: RotatorRequest) -> RotatorResponse:
        """Synchronously select the next healthy session.

        Owns the event-loop handling inside the capability so a sync
        caller (the orchestrator's ``execute`` seam) never calls
        ``asyncio.run`` inline.
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
    "ISessionLoginCheckerProtocol",
    "ISessionLimitCheckerProtocol",
    "ISessionRotatorProtocol",
    "ISessionRenewalProtocol",
    "IProfilePreparerProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "ISessionManagerProtocol": ISessionManagerProtocol,
    "ISessionLoginCheckerProtocol": ISessionLoginCheckerProtocol,
    "ISessionLimitCheckerProtocol": ISessionLimitCheckerProtocol,
    "ISessionRotatorProtocol": ISessionRotatorProtocol,
    "ISessionRenewalProtocol": ISessionRenewalProtocol,
    "IProfilePreparerProtocol": IProfilePreparerProtocol,
}
