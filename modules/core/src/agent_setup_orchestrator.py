"""Agent: setup orchestrator (AES405).

Orchestrates interactive GUI manual login session setup.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from modules.core.src.utility_core_config_factory import build_app_config
from modules.shared.src.contract_core_aggregate import ISetupAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IObservabilityProtocol,
)
from modules.shared.src.taxonomy_core_constant import CHAT_URL, DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import AppConfig, ResponseText


class SetupOrchestrator(ISetupAggregate):
    """Orchestrates interactive manual login and CAPTCHA setup."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        self._browser = browser
        self._observability = observability

    def setup_session(
        self,
        wait_for_confirmation: Callable[[], None] | None = None,
        session_path: Path | None = None,
    ) -> ResponseText:
        """Validate or establish a persistent manual login session."""
        cfg = build_app_config(
            mode="login",
            input_path=DEFAULT_OUTPUT,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=False,
        )

        if cfg.session_path.is_dir() and self._validate_saved_session(cfg):
            return ResponseText("An existing saved Qwen session is already valid. No visible browser was opened.")

        with self._browser.browser_session(cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded")

            if callable(wait_for_confirmation):
                wait_for_confirmation()

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
                    sleep_ms = min(500, max(100, int(remaining * 1000)))
                    page.wait_for_timeout(sleep_ms)
                except Exception:
                    break

        if self._validate_saved_session(cfg):
            return ResponseText("Manual login completed successfully. The Qwen session is valid for headless tasks.")

        return ResponseText(
            "Manual login did not produce a valid Qwen session. Please run 'qwen-web-arwaky --login' "
            "again and finish the login or CAPTCHA."
        )

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
