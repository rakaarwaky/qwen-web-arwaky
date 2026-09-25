"""Agent: session orchestrator (AES405).

Orchestrates session validation and deletion using browser protocol.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from modules.core.src.utility_core_config_factory import build_app_config
from modules.core.src.utility_core_session_guard import is_safe_session_target
from modules.shared.src.contract_core_aggregate import ISessionAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IObservabilityProtocol,
)
from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_error import QwenCliError
from modules.shared.src.taxonomy_core_vo import AppConfig, ResponseText


class SessionOrchestrator(ISessionAggregate):
    """Orchestrates Qwen session checking and deletion."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        self._browser = browser
        self._observability = observability

    def validate_session(self, session_path: Path | None = None) -> tuple[bool, str]:
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

    def delete_session(self, session_path: Path | None = None) -> ResponseText:
        """Delete persistent session profile from disk after path safety checks.

        The target must be an existing directory that clears every rule in
        :func:`is_safe_session_target`: not a filesystem root (``/``,
        ``C:\\``), not a near-root path such as ``/etc`` or ``C:\\Windows``,
        and either the application session directory or a safe session name
        under the user's home. Everything else is refused before ``rmtree``
        is ever reached, so no path-traversal or Windows drive-root delete is
        possible.
        """
        cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=True,
        )
        target = cfg.session_path.resolve()
        if not target.exists():
            return ResponseText("No session found to delete.")

        # Refuse before touching the filesystem: roots, near-root paths,
        # non-directories, home itself, and any path outside the allow-list.
        if not is_safe_session_target(target):
            raise QwenCliError(f"Refusing to delete unsafe session path: {target}")

        try:
            shutil.rmtree(target)
            return ResponseText("Session deleted successfully.")
        except Exception as exc:
            # A partial rmtree leaves the profile in an inconsistent state;
            # surface the failure and the residue so the operator can remove
            # it by hand instead of silently losing the rest of the tree.
            raise QwenCliError(
                f"Failed to delete session {target}: {exc}. "
                "Deletion may be partial — remove the remaining directory manually."
            ) from exc

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
            self._observability.get_logger().debug("saved_session_validation_failed", error=str(exc))
            return False


__all__ = ["SessionOrchestrator"]
