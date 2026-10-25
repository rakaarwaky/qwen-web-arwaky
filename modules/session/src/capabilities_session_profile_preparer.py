"""Session profile preparation — mode→clone decision for browser profiles.

Capabilities layer: owns the ephemeral profile clone decision. Imports the
session contract protocol IProfilePreparerProtocol (contract) and the shared
utility_session_cloner (session→shared, allowed). The browser capability no
longer imports session utilities; it receives a plain prepared Path from this
capability.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from modules.shared.src.common.taxonomy_core_vo import AppConfig
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.session.contract_session_protocol import IProfilePreparerProtocol
from modules.shared.src.session.utility_session_cloner import create_ephemeral_session

log = get_logger("session_profile_preparer")


class ProfilePreparer(IProfilePreparerProtocol):
    """Prepares a session profile path for browser launch.

    Owns the mode→clone decision:
    - login mode → the master session path directly (credentials persist)
    - standard runs/jobs → an ephemeral clone of the master profile so
      multiple browser processes can run concurrently without SingletonLock
      conflicts.
    """

    # Block 1: Class Definition & Constructor

    def __init__(self) -> None:
        """Initialize the profile preparer."""
        return None

    # Block 2: Protocol Trait Implementation

    def prepare(self, cfg: AppConfig) -> AbstractContextManager[Path]:
        """Return a context manager that yields a prepared session profile path.

        For login mode, yields the master session path directly.
        For standard modes, clones the master into an ephemeral temp dir
        and yields the clone path (cleaned up on exit).
        """
        return self._prepare(cfg)

    @contextmanager
    def _prepare(self, cfg: AppConfig) -> Iterator[Path]:
        master_session = cfg.session_path
        mode = getattr(cfg, "mode", "")
        if mode == "login":
            log.debug("profile_preparer_login_mode_master_path", path=str(master_session))
            yield master_session
            return
        with create_ephemeral_session(master_session, mode=mode) as session_dir:
            log.debug(
                "profile_preparer_standard_mode_clone",
                master=str(master_session),
                clone=str(session_dir),
            )
            yield session_dir

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of ProfilePreparer."""
        return "ProfilePreparer()"


__all__ = ["ProfilePreparer"]
