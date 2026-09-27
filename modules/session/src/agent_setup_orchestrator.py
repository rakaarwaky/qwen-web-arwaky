"""Agent: setup orchestrator (AES405).

Implements :class:`ISetupAggregate` — the single entry point over the
interactive manual-login feature. A surface holds this one object and
calls :meth:`execute` with a ``SetupRequest``; the orchestrator owns the
launch → navigate → wait → validate → snapshot sequence, so no surface can
skip the session check every manual-login run depends on.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from modules.config.src.utility_config_app_factory import build_app_config
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
)
from modules.shared.src.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.contract_setup_aggregate import ISetupAggregate
from modules.shared.src.taxonomy_core_constant import CHAT_URL, DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.taxonomy_setup_vo import SetupRequest, SetupResponse
from modules.shared.src.utility_core_session_backup import take_snapshot


class SetupOrchestrator(ISetupAggregate):
    """Orchestrates interactive manual login and CAPTCHA setup."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        self._browser = browser
        self._observability = observability

    def execute(self, request: SetupRequest) -> SetupResponse:
        """Validate or establish a persistent manual login session."""
        profile_path = request.profile_path
        cfg = build_app_config(
            mode="login",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=Path(profile_path) if profile_path is not None else None,
            headless=request.browser_headless,
        )

        if cfg.session_path.is_dir() and self._validate_saved_session(cfg):
            return SetupResponse(success=True, profile_path=str(cfg.session_path), message="Session already valid.")

        with self._browser.browser_session(cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded")

            deadline = time.monotonic() + cfg.timeout
            while True:
                try:
                    if page.is_closed():
                        break
                except Exception:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    # Ask the caller (e.g. the TUI worker) whether the manual
                    # login is complete. When it returns True we break out of
                    # the loop; when it returns False we keep waiting.
                    # ``wait_for_confirmation`` is a zero-arg callable that
                    # returns a bool — a simple sentinel for the TUI flow.
                    if request.wait_for_confirmation is not None and request.wait_for_confirmation():
                        break
                    sleep_ms = min(500, max(100, int(remaining * 1000)))
                    page.wait_for_timeout(sleep_ms)
                except Exception:
                    break

        if self._validate_saved_session(cfg):
            try:
                take_snapshot(cfg.session_path)
            except Exception as exc:
                self._observability.get_logger().warning(
                    "session_backup_failed", error=str(exc), session_path=str(cfg.session_path)
                )
            return SetupResponse(
                success=True,
                profile_path=str(cfg.session_path),
                message="Manual login completed successfully.",
            )

        return SetupResponse(
            error=(
                "Manual login did not produce a valid Qwen session. "
                "Please run 'qwen-web-arwaky --login' again and finish the login or CAPTCHA."
            ),
        )

    def setup_session(
        self,
        wait_for_confirmation: Callable[[], bool] | None = None,
        session_path: Path | None = None,
    ) -> str:
        """Return the login outcome as text, delegating to :meth:`execute`.

        ``wait_for_confirmation`` is passed to :meth:`execute` so the setup
        loop can hold the browser open inside its context until the caller
        signals the manual login is complete; headless and CLI callers leave
        it ``None`` and the browser-close check runs immediately.
        """
        response = self.execute(
            SetupRequest(
                profile_path=session_path,
                wait_for_confirmation=wait_for_confirmation,
            )
        )
        return str(response.error or response.message or response.profile_path or "")

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


__all__ = ["SetupOrchestrator"]
