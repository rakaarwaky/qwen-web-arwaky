"""Browser model-selection capability (Playwright adaptation).

Capabilities layer: implements IBrowserModelPolicyProtocol. Imports taxonomy,
contract(protocol), and utility only.

Owns the issue #283/#374 model-selection/verification fallback rules —
product policy about which model a run targets and how the picker degrades
when the configured model is absent — keeping the DOM mechanics out of the
browser adapter. The per-run target model is carried in the shared
``utility_browser_model_target`` contextvar (bound once per browser context
launch by the browser adapter), so concurrent runs keep their own override
without mutating shared state.
"""

from __future__ import annotations

import contextlib
from typing import Any

from playwright.sync_api import Error, Page

from modules.shared.src.browser.contract_browser_protocol import IBrowserModelPolicyProtocol
from modules.shared.src.browser.utility_browser_model_target import bind_target_model, target_model
from modules.shared.src.common.taxonomy_core_constant import DEFAULT_MODEL, MODEL_SELECTOR_BUTTON
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import ModelSwitchError
from modules.shared.src.common.taxonomy_core_vo import ModelLabel, WaitTimeoutMs
from modules.shared.src.common.utility_logger_factory import get_logger

log = get_logger("browser.model_policy")

# Block 1: Class Definition & Constructor


class BrowserModelPolicy(IBrowserModelPolicyProtocol):
    """Model selection/verification policy behind the browser contract."""

    def __init__(self) -> None:
        """Initialize BrowserModelPolicy."""
        pass

    # Block 2: Public Contract

    def select_model(self, page: Page, emitter: LifecycleEmitter) -> ModelLabel:
        """Read/select the default model on *page*; return the chosen label.

        Raises:
            ModelSwitchError: When no model label can be read at all.
        """
        del emitter
        target = target_model()
        bind_target_model(target)
        self.ensure_default_model(page)
        verified, detected = self.verify_default_model(page, target, require_switch=False)
        return target if verified else detected

    def verify_model(self, page: Page, expected: ModelLabel) -> bool:
        """Return True when *page* shows *expected* as the active model."""
        try:
            picker = self.get_model_trigger(page)
            picker.wait_for(state="visible", timeout=5000)
            current = (picker.inner_text() or "").replace("\n", " ").strip()
            return expected in current.split()
        except Error:
            return False

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of BrowserModelPolicy."""
        return "BrowserModelPolicy()"

    def ensure_default_model(self, page: Page) -> bool:
        """Best-effort: ensure the active Qwen model is the configured default.

        Opens the model picker only long enough to click the default option.
        The call is defensive — any failure is logged and swallowed so it can
        never block the prompt pipeline (the verify step then drives
        fallback).
        """
        target = target_model()
        try:
            picker = self.get_model_trigger(page)
            picker.wait_for(state="visible", timeout=5000)
            picker.click(timeout=5000)

            # Option item (.wms-list__item or role=option)
            option = page.get_by_role("option", name=target)
            with contextlib.suppress(Error):
                loc = page.locator(".wms-list__item", has_text=target).first
                if loc.is_visible(timeout=1000) is True:
                    option = loc

            option.wait_for(state="visible", timeout=5000)
            option.click(timeout=5000)
            page.wait_for_timeout(300)

            self.try_set_as_default(page)
            log.debug("ensure_default_model_applied %s", target)
            return True
        except Error as exc:
            log.debug("ensure_default_model_skipped %s %s", target, str(exc))
            return False

    def verify_default_model(
        self, page: Page, target: ModelLabel, require_switch: bool = True
    ) -> tuple[bool, ModelLabel]:
        """Confirm the active model is *target*, degrading when it is not.

        Runs after ``ensure_default_model`` so a silent picker failure cannot
        let the pipeline dispatch the prompt to an unrecorded model. Returns
        ``(True, target)`` when the configured default is active. When the
        configured model is absent from the picker, the first available
        model is selected and a WARNING is logged (issue #283 AC-2); the
        method then returns ``(False, fallback)`` so the caller can proceed
        with the active model instead of aborting the pipeline (issue #374).
        Raises ``ModelSwitchError`` only when no model label can be read at
        all, since the active model is then unknowable. When the best-effort
        switch reported failure (``require_switch=False``), verification is
        retried while the model picker hydrates so a slow picker cannot fail
        the pipeline.
        """
        # Model picker options can arrive after the committed page document,
        # especially when Qwen's static assets are slow. Keep this readiness
        # gate bounded and retry selection instead of failing the whole
        # pipeline on the first stale model label.
        attempts = 5
        current = ""
        for attempt in range(attempts):
            try:
                picker = self.get_model_trigger(page)
                picker.wait_for(state="visible", timeout=5000)
                current = (picker.inner_text() or "").replace("\n", " ").strip()
            except Error as exc:
                if attempt + 1 < attempts:
                    log.debug("verify_default_model_read_retry %s %s %s", target, str(exc), attempt + 1)
                    self.retry_default_model_selection(page)
                    continue
                fallback = self.select_first_available_model(page)
                if fallback is not None:
                    return False, fallback
                raise ModelSwitchError(
                    f"Cannot read active model from '{MODEL_SELECTOR_BUTTON}' button: {exc}"
                ) from exc
            if target in current.split():
                log.debug("verify_default_model_ok %s", target)
                return True, target
            if attempt + 1 < attempts:
                log.debug("verify_default_model_retry %s %s %s %s", target, current, require_switch, attempt + 1)
                self.retry_default_model_selection(page)
                continue
            # FRD FR-001 fallback: the configured default is absent from the
            # picker, so pipeline availability wins over exact matching
            # (issue #374). Prefer actively selecting the first available
            # model so the run continues on a known-good picker entry
            # (issue #283).
            fallback = self.select_first_available_model(page)
            if fallback is not None:
                return False, fallback
            log.warning(
                "default_model_unavailable_proceeding_with_active %s %s",
                target,
                current,
            )
            return False, ModelLabel(current)
        fallback = self.select_first_available_model(page)
        if fallback is not None:
            return False, fallback
        raise ModelSwitchError(f"Default model not active: expected '{target}'")

    def select_first_available_model(self, page: Page) -> ModelLabel | None:
        """Select the first model the picker offers, or return None when unreadable.

        The graceful-degradation path for a renamed or deprecated model
        identifier (issue #283 AC-2): the run continues on whatever model the
        picker exposes first, and the WARNING names both the configured and
        the active model so the discrepancy is auditable.
        """
        try:
            picker = self.get_model_trigger(page)
            picker.click(timeout=5000)
            try:
                first_option = page.locator(".wms-list__item").first
                if first_option.is_visible(timeout=2000) is not True:
                    return None
                label = (first_option.inner_text() or "").replace("\n", " ").strip()
                first_option.click(timeout=5000)
            finally:
                with contextlib.suppress(Error):
                    page.keyboard.press("Escape")
        except Error as exc:
            log.warning("model_fallback_unavailable %s %s", target_model(), str(exc))
            return None
        if not label:
            return None
        log.warning(
            "model_fallback_activated %s %s %s",
            target_model(),
            label,
            "configured model not offered by the model picker",
        )
        return ModelLabel(label)

    def wait_for_picker_ready(self, page: Page, timeout_ms: WaitTimeoutMs = WaitTimeoutMs(15_000)) -> None:
        """Wait until the hydrated picker exposes the configured default option."""
        target = target_model()
        picker = self.get_model_trigger(page)
        picker.wait_for(state="visible", timeout=timeout_ms)
        picker.click(timeout=5000)
        try:
            option: Any = page.get_by_role("option", name=target)
            with contextlib.suppress(Error):
                loc = page.locator(".wms-list__item", has_text=target).first
                if loc.is_visible(timeout=1000) is True:
                    option = loc
            option.wait_for(state="visible", timeout=timeout_ms)
        finally:
            with contextlib.suppress(Error):
                page.keyboard.press("Escape")

    def retry_default_model_selection(self, page: Page) -> None:
        """Close a stale picker, allow hydration, and retry default-model selection."""
        with contextlib.suppress(Error):
            page.keyboard.press("Escape")
            page.wait_for_timeout(2000)
        self.ensure_default_model(page)

    def get_model_trigger(self, page: Page) -> Any:
        """Return locator for active model selector trigger button/div."""
        with contextlib.suppress(Error):
            trigger = page.locator(".wms-trigger, [aria-label='Select Model']").first
            if trigger.is_visible(timeout=1000) is True:
                return trigger
        return page.get_by_role("button", name=MODEL_SELECTOR_BUTTON)

    def try_set_as_default(self, page: Page) -> None:
        """Best-effort attempt to click 'Set default' or 'Set as default' in Qwen UI picker."""
        try:
            picker = self.get_model_trigger(page)
            picker.click(timeout=3000)
            page.wait_for_timeout(300)

            with contextlib.suppress(Error):
                item = page.locator(".wms-list__item", has_text=DEFAULT_MODEL).first
                if item.is_visible(timeout=1500) is True:
                    pin = item.locator(".wms-list__pin-action, :has-text('Set as default')").first
                    if "Set as default" in (pin.inner_text() or ""):
                        pin.evaluate("e => e.click()")
                        log.debug("set_default_model_ui_applied %s", target_model())
                        page.wait_for_timeout(300)

            with contextlib.suppress(Error):
                page.keyboard.press("Escape")
        except Error as exc:
            log.debug("set_default_model_ui_skipped %s", str(exc))
            with contextlib.suppress(Error):
                page.keyboard.press("Escape")


__all__ = ["BrowserModelPolicy"]
