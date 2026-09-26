"""Capabilities: prompt injection via DOM (AES403).

Implements IInjectionProtocol.
"""

from __future__ import annotations

import contextlib
from typing import Any

from playwright.sync_api import Error, Page

from modules.shared.src.contract_core_protocol import IInjectionProtocol
from modules.shared.src.taxonomy_core_error import ElementNotFoundError, PromptInjectionError
from modules.shared.src.taxonomy_core_vo import DEFAULT_INJECTOR_CONFIG, InjectorConfig
from modules.shared.src.utility_dom_helper import first_visible_element_handle
from modules.shared.src.utility_logger_factory import get_logger

log = get_logger("capabilities_prompt_injector")


# Block 1: Class Definition & Constructor


class PromptInjector(IInjectionProtocol):
    """Multi-strategy DOM text injection with verification."""

    def __init__(self, config: InjectorConfig = DEFAULT_INJECTOR_CONFIG) -> None:
        """Initialize with an InjectorConfig VO."""
        self.config = config

    # ─── Block 2: Public Contract (IInjectionProtocol ONLY) ──
    def find_input(self, page: Page, config: InjectorConfig | None = None) -> Any:
        """Find input element using selector fallbacks."""
        cfg = config or self.config
        selectors = tuple(cfg.input_selectors)
        start_timeout = max(1000, int(cfg.wait_timeout_ms) // len(selectors))

        el = first_visible_element_handle(page, selectors, start_timeout)
        if el:
            return el

        # Final attempt with full timeout on primary selector
        primary = selectors[0]
        try:
            el = page.wait_for_selector(primary, timeout=int(cfg.wait_timeout_ms))
            if el:
                return el
        except (TimeoutError, Error) as e:
            raise ElementNotFoundError(f"Timed out waiting for input selector '{primary}' on chat.qwen.ai: {e}") from e
        raise ElementNotFoundError("Could not locate input element on chat.qwen.ai. UI may have changed.")

    def inject_text(self, page: Page, text: str, config: InjectorConfig | None = None) -> None:
        """Inject text into input via multi-tier strategy in 4 sequential steps:

        Step 1: Validate input text & locate target element
        Step 2: Strategy 0 — Playwright fill & React dispatch
        Step 3: Strategy 1 — React value setter fallback
        Step 4: Strategy 2 — Playwright type() fallback
        """
        # Step 1: Validate prompt text & locate input element
        if not text or not text.strip():
            raise PromptInjectionError("Cannot inject empty or whitespace-only prompt text.")

        cfg = config or self.config
        el = self.find_input(page, cfg)

        # Step 2: Strategy 0 — Playwright fill & React dispatch
        try:
            with contextlib.suppress(Exception):
                el.click()
                el.focus()
            el.fill(text)
            with contextlib.suppress(Exception):
                el.dispatch_event("input")
                el.dispatch_event("change")
                el.dispatch_event("keyup")
            if not self._verify_injection(el):
                with contextlib.suppress(Exception):
                    page.keyboard.insert_text(text)
            if not cfg.verify_injection or self._verify_injection(el):
                log.info("Prompt injected via Playwright fill (%d chars)", len(text))
                return
        except Error as e:
            log.debug("Initial Playwright fill failed; trying DOM injection strategies: %s", e)

        # Step 3: Strategy 1 — React value setter fallback
        js_react_inject = """(text) => {
            const selectors = ['textarea.message-input-textarea', 'textarea', 'div[contenteditable="true"]', '#chat-input'];
            let target = null;
            for (const s of selectors) {
                const found = document.querySelector(s);
                if (found) { target = found; break; }
            }
            if (!target) return false;
            if (target.tagName.toLowerCase() === 'textarea' || target.tagName.toLowerCase() === 'input') {
                const proto = target.tagName.toLowerCase() === 'textarea' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                if (descriptor && descriptor.set) {
                    descriptor.set.call(target, text);
                } else {
                    target.value = text;
                }
                if (target._valueTracker) {
                    target._valueTracker.setValue('');
                }
                target.dispatchEvent(new Event('input', { bubbles: true }));
                target.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            } else if (target.isContentEditable) {
                target.innerText = text;
                target.dispatchEvent(new Event('input', { bubbles: true }));
                return true;
            }
            return false;
        }"""

        try:
            success = page.evaluate(js_react_inject, text)
            if success and (not cfg.verify_injection or self._verify_injection(el)):
                log.info("Prompt injected via React value-setter (%d chars)", len(text))
                return
        except Error as e:
            log.debug("React value-setter strategy bypassed/failed: %s", e)

        # Step 4: Strategy 2 — Playwright type() fallback
        try:
            log.debug("Falling back to Playwright type()")
            el.type(text, delay=cfg.typing_delay_ms)
            if not cfg.verify_injection or self._verify_injection(el):
                log.info("Prompt injected via Playwright type() (%d chars)", len(text))
                return
        except Error as exc:
            raise PromptInjectionError(f"All strategies failed for prompt: {exc}") from exc

        raise PromptInjectionError("All strategies executed but input verification failed.")

    # Block 3: Dunder Methods, Factories & Helpers

    def _verify_injection(self, el: Any) -> bool:
        """Verify that text is non-empty inside the input element."""
        try:
            val = el.evaluate("(el) => el.value !== undefined ? el.value : (el.innerText || el.textContent || '')")
            return bool(val and len(str(val).strip()) > 0)
        except Exception:
            return False

    def __repr__(self) -> str:
        """Return string representation of PromptInjector."""
        return f"PromptInjector(config={self.config!r})"
