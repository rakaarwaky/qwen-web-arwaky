"""Capabilities: send button dispatcher (AES403).

Implements ISendProtocol.
"""

from __future__ import annotations

import contextlib
import time

from playwright.sync_api import Error, Page

from modules.core.src.utility_core_dom_helper import click_send as _dom_click_send
from modules.core.src.utility_core_dom_query import count_messages, latest_message_text
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import ISendProtocol
from modules.shared.src.taxonomy_core_constant import TEXTAREA_SELECTOR
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_error import SendDispatchError
from modules.shared.src.taxonomy_core_event import EVENT_DISPATCH_ACKNOWLEDGED, EVENT_SEND_CLICKED
from modules.shared.src.taxonomy_core_vo import (
    ClickTimeoutMs,
    MessageCount,
    ResponseText,
    SenderConfig,
    TryEnterKeyFallbackFlag,
)

log = get_logger("capabilities_send_dispatcher")


def _is_parse_toast_visible(page: Page) -> bool:
    """Safely check if Qwen's document parsing warning toast is visible."""
    toast_selectors = (
        ".ant-message",
        "[role='alert']",
        "[class*='toast']",
        "[class*='notification']",
        "[class*='message-notice']",
        "[class*='alert']",
        "body",
    )
    parse_keywords = (
        "still uploading",
        "upload to complete",
        "currently parsing",
        "parsing file",
        "wait until",
        "files still",
        "uploading",
    )
    for selector in toast_selectors:
        try:
            locator = page.locator(selector)
            c = locator.count()
            if not isinstance(c, int) or c == 0:
                continue
            for i in range(min(c, 5)):
                item = locator.nth(i)
                if item.is_visible(timeout=100):
                    text = item.inner_text(timeout=100).casefold()
                    if any(kw in text for kw in parse_keywords):
                        return True
        except Exception:
            pass
    return False


def _is_file_card_parsing(page: Page) -> bool:
    """Return True if any file card in the composer input area still shows a Parsing indicator or spinner."""
    card_selectors = (
        ".message-input-column-file",
        ".file-card-list",
        "[class*='fileitem']",
        "[class*='file-card']",
        "[class*='file-item']",
        "[class*='attachment']",
        "[class*='composer']",
        "[class*='input']",
    )
    for sel in card_selectors:
        try:
            loc = page.locator(sel)
            c = loc.count()
            if not isinstance(c, int) or c == 0:
                continue
            for i in range(min(c, 10)):
                item = loc.nth(i)
                if not item.is_visible(timeout=100):
                    continue
                text = item.inner_text(timeout=100).casefold()
                if "parsing" in text or "processing" in text or "uploading" in text:
                    return True
                spinners = item.locator(
                    "svg[class*='spin'], svg[class*='loading'], .ant-spin, [class*='loading'], [class*='parsing'], [class*='spin']"
                )
                if spinners.count() > 0 and spinners.first.is_visible(timeout=100):
                    return True
        except Exception:
            pass
    return False


# Block 1: Class Definition & Constructor


class SendDispatcher(ISendProtocol):
    """Multi-strategy send button trigger with keyboard fallback."""

    def __init__(
        self,
        click_timeout_ms: ClickTimeoutMs = ClickTimeoutMs(10000),
        try_enter_key_fallback: TryEnterKeyFallbackFlag = TryEnterKeyFallbackFlag(True),
    ) -> None:
        self.click_timeout_ms = click_timeout_ms
        self.try_enter_key_fallback = try_enter_key_fallback

    # ─── Block 2: Public Contract (ISendProtocol ONLY) ──
    def click_send(
        self,
        page: Page,
        emitter: LifecycleEmitter,
        config: SenderConfig | None = None,
        document_parsed: bool = True,
    ) -> None:
        """Click prompt send button in 4 sequential steps:

        Step 1: Check document parse gate
        Step 2: Wait for send button enabled & parse toast clear
        Step 3: Trigger DOM send click & emit EVENT_SEND_CLICKED
        Step 4: Verify dispatch acknowledgment (with Enter fallback)
        """
        # Step 1: Check document parse gate
        if not document_parsed:
            raise SendDispatchError(
                "Cannot send prompt: document attachment parsing (EVENT_DOCUMENT_PARSED) is incomplete"
            )

        effective_config = config or SenderConfig(
            click_timeout_ms=int(self.click_timeout_ms),
            try_enter_key_fallback=bool(self.try_enter_key_fallback),
        )

        deadline = time.monotonic() + (effective_config.click_timeout_ms / 1000)
        while time.monotonic() < deadline:
            # Step 2: Wait for send button enabled & no active parse toast
            self._wait_for_send_enabled(page, timeout_ms=effective_config.click_timeout_ms)
            baseline_count = int(count_messages(page))
            baseline_text = latest_message_text(page)

            # Step 3: Trigger DOM send click
            if not _dom_click_send(page, _config=effective_config):
                raise SendDispatchError("Unable to dispatch prompt: send button and Enter fallback both failed")

            page.wait_for_timeout(300)
            if _is_parse_toast_visible(page):
                log.info("Document parsing is still in progress (Qwen toast displayed). Waiting for completion...")
                page.wait_for_timeout(1000)
                continue

            details: dict[str, object] = {"selector": "SendDispatcher"}
            emitter.emit(EVENT_SEND_CLICKED, details)

            # Step 4: Verify dispatch acknowledgment (with Enter fallback if needed)
            if not self._wait_for_dispatch_ack(
                page, baseline_count, baseline_text, timeout_ms=int(effective_config.click_timeout_ms)
            ):
                if _is_parse_toast_visible(page):
                    page.wait_for_timeout(1000)
                    continue
                try:
                    textarea = page.locator(TEXTAREA_SELECTOR).first
                    textarea.press("Enter")
                except (Error, TimeoutError):
                    with contextlib.suppress(Error, TimeoutError):
                        page.keyboard.press("Enter")
                if not self._wait_for_dispatch_ack(
                    page, baseline_count, baseline_text, timeout_ms=int(effective_config.click_timeout_ms)
                ):
                    if _is_parse_toast_visible(page):
                        page.wait_for_timeout(1000)
                        continue
                    raise SendDispatchError("Send control was clicked but Qwen did not acknowledge the user turn")
            emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, details)
            return

        raise SendDispatchError("Send control dispatch timed out waiting for document parsing or user turn ACK")

    def _wait_for_dispatch_ack(
        self,
        page: Page,
        baseline_count: int,
        baseline_text: ResponseText | None,
        timeout_ms: int | None = None,
    ) -> bool:
        """Verify that the click produced a real new user turn.

        A cleared composer or disabled send button is not sufficient evidence:
        Qwen can reset either control before the user turn is committed. The
        acknowledgment must come from a new turn count or a changed message
        surface so the response monitor cannot wait on a false dispatch.
        """
        from modules.core.src.utility_core_dom_query import latest_message_text as _latest_message_text

        effective_timeout = timeout_ms if timeout_ms is not None else int(self.click_timeout_ms)
        deadline = time.monotonic() + (effective_timeout / 1000)
        while time.monotonic() < deadline:
            try:
                if int(count_messages(page)) > baseline_count:
                    return True
                current_text = _latest_message_text(page)
                if current_text is not None and str(current_text).strip() and current_text != baseline_text:
                    return True
            except (Error, TimeoutError):
                pass
            page.wait_for_timeout(100)
        return False

    def _wait_for_send_enabled(self, page: Page, timeout_ms: int = 5000) -> bool:
        """Wait until send is safe: no file parsing in progress AND button is enabled."""
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            try:
                # Proactive check: file card still shows "Parsing..." in DOM
                if _is_file_card_parsing(page):
                    log.debug("File card still parsing — holding send.")
                    page.wait_for_timeout(500)
                    continue

                # Reactive check: toast appeared after a premature click attempt
                if _is_parse_toast_visible(page):
                    log.debug("Parse toast visible — holding send.")
                    page.wait_for_timeout(500)
                    continue

                for selector in (
                    ".message-input-right-button-send button:not([disabled]):not(.disabled)",
                    "button.send-button:not([disabled]):not(.disabled)",
                    "button[aria-label*='Send' i]:not([disabled]):not(.disabled)",
                    "button[type='submit']:not([disabled]):not(.disabled)",
                    "button[class*='send' i]:not([disabled]):not(.disabled)",
                ):
                    loc = page.locator(selector).first
                    c = loc.count()
                    if isinstance(c, int) and c > 0 and loc.is_visible(timeout=100) and loc.is_enabled(timeout=100):
                        return True
            except (Error, TimeoutError):
                pass
            page.wait_for_timeout(200)
        return False

    def count_messages(self, page: Page) -> MessageCount:
        """Count chat turns using JS evaluate."""
        return count_messages(page)

    def latest_message_text(self, page: Page) -> ResponseText | None:
        """Get the longest text block on page excluding input/UI chrome."""
        return latest_message_text(page)

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of SendDispatcher."""
        return f"SendDispatcher(timeout={self.click_timeout_ms}, fallback={self.try_enter_key_fallback})"
