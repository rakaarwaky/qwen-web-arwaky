"""Agent: session orchestrator (AES405).

Orchestrates session validation and deletion using browser protocol.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
)
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.contract_session_aggregate import ISessionAggregate
from modules.shared.src.contract_session_protocol import ISessionManagerProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.taxonomy_session_vo import (
    SessionRequest,
    SessionResponse,
)
from modules.shared.src.utility_config_app_factory import build_app_config


class SessionOrchestrator(ISessionAggregate):
    """Orchestrates Qwen session checking and deletion."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        observability: IObservabilityProtocol,
        sessions: ISessionManagerProtocol,
    ) -> None:
        self._browser = browser
        self._observability = observability
        self._sessions = sessions

    # Block 2: Protocol Method Implementation

    def execute(self, request: SessionRequest) -> SessionResponse:
        """Run the requested session verb and return its outcome.

        Routes on ``request.verb``: ``validate`` runs the headless auth
        check and returns the verdict; ``delete`` runs the path-safety
        guard, then removes the profile. All I/O is delegated to the
        browser capability — this agent only routes and wraps results.
        """
        if request.verb == "validate":
            valid, message = self._validate(request.session_path)
            return SessionResponse(valid=valid, message=message)
        if request.verb == "delete":
            message = self._delete(request.session_path, force=request.force)
            return SessionResponse(deleted=True, message=message)
        return SessionResponse(error=f"unknown session verb: {request.verb!r}")

    # Block 3: Dunder Methods, Factories, Helpers

    def _validate(self, session_path: Path | None) -> tuple[bool, str]:
        """Validate an existing saved Qwen browser session in headless mode."""
        cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=True,
        )
        if not cfg.session_path.is_dir():
            return False, "Session not found. Please log in first."
        if self._validate_saved_session(cfg):
            return True, "Saved Qwen session is valid and ready to use."
        return False, "Saved Qwen session is invalid or expired. Please log in again."

    def _delete(self, session_path: Path | None, *, force: bool) -> str:
        """Delete the saved Chromium profile for *session_path*.

        Every safety rule lives in the session manager that owns the profile
        on disk: the target must be an existing directory that clears
        ``is_safe_session_target`` (never a filesystem root, a near-root path
        such as ``/etc``, or a path outside the allow-list), and deletion is
        refused while no backup generation is retained unless the caller passes
        ``force=True`` (issue #300).
        """
        cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=True,
        )
        delete_profile = self._sessions.delete_session_profile
        delete_profile(cfg.session_path, force=force)
        return "Session deleted successfully."

    def _validate_saved_session(self, cfg: AppConfig) -> bool:
        """Check an existing profile without opening a visible login window."""
        validation_cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=cfg.session_path,
            headless=True,
        )
        try:
            with self._browser.browser_session(validation_cfg) as bctx:
                page = bctx.pages[0] if bctx.pages else bctx.new_page()
                emitter = LifecycleEmitter(self._observability.get_logger())
                self._browser.navigate_to_chat(page, emitter)
                return self._browser.check_session(page)
        except Exception as exc:
            log_debug = self._observability.get_logger().debug
            log_debug("saved_session_validation_failed", error=str(exc))
            return False


__all__ = ["SessionOrchestrator"]
