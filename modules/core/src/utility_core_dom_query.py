"""DOM query utilities for Playwright pages.

Utility layer (utility_core_dom_query): stateless functions for DOM reading.
Consumed by SendDispatcher, StreamMonitor, and Agent.
Taxonomy constants + Playwright Page only.
"""

from __future__ import annotations

import re

from playwright.sync_api import Error, Page

from modules.shared.src.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    RESPONSE_CONTENT_SELECTOR,
)
from modules.shared.src.taxonomy_core_vo import MessageCount, ResponseText

_PAGINATION_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")


def count_messages(page: Page) -> MessageCount:
    """Count chat turns via injected JS with locator fallback.

    Tier 1: injected JS (JS_COUNT_TURNS) when it yields a positive int.
    Tier 2: combined message-selector locator count.
    Fallback: MessageCount(0).

    Returns
    -------
    MessageCount
        Number of message elements matching turn selectors.

    """
    try:
        count = page.evaluate(JS_COUNT_TURNS)
        if isinstance(count, int) and count > 0:
            return MessageCount(count)
    except Error:
        pass
    try:
        return MessageCount(page.locator(COMBINED_MESSAGE_SELECTOR).count())
    except Error:
        return MessageCount(0)


def latest_message_text(page: Page) -> ResponseText | None:
    """Extract the latest assistant response text via injected JS with locator fallback.

    Tier 1: injected JS (JS_GET_RESPONSE_TEXT) when it yields non-empty text.
    Tier 2: combined message-selector locator's last text content.
    Tier 3: paginated-response fallback — concatenates all page segments.
    Fallback: None.

    Returns
    -------
    ResponseText | None
        Trimmed text, or None when nothing is available.

    """
    try:
        text = page.evaluate(JS_GET_RESPONSE_TEXT)
        if text and isinstance(text, str) and len(text.strip()) > 0:
            stripped = text.strip()
            if not _PAGINATION_RE.match(stripped):
                return ResponseText(stripped)
    except Error:
        pass
    try:
        locator = page.locator(RESPONSE_CONTENT_SELECTOR)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None and isinstance(text, str):
                stripped = text.strip()
                if not _PAGINATION_RE.match(stripped):
                    return ResponseText(stripped)
    except Error:
        pass

    # Tier 3: Pagination fallback — collect text from all response segments
    try:
        segments: list[str] = []
        selector = (
            ".qwen-markdown, .qwen-chat-message-assistant, .chat-response-message, "
            ".chat-message-assistant, [data-role='assistant'], .response-message-content"
        )
        nodes = page.locator(selector)
        count = nodes.count()
        for i in range(count):
            node = nodes.nth(i)
            if node.evaluate("el => !!el.closest('.qwen-chat-message-user')"):
                continue
            txt = node.text_content()
            if txt and not _PAGINATION_RE.match(txt.strip()):
                segments.append(txt.strip())
        if segments:
            return ResponseText("\n\n".join(segments))
    except Error:
        pass
    return None
