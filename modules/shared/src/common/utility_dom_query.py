"""DOM query utilities for Playwright pages.

Utility layer (utility_dom_query): stateless functions for DOM reading.
Consumed by SendDispatcher, StreamMonitor, and Agent.
Taxonomy constants + Playwright Page only.
"""

from __future__ import annotations

import re

from playwright.sync_api import Error, Page

from modules.shared.src.common.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    RESPONSE_CONTENT_SELECTOR,
    USER_COMBINED_SELECTOR,
)
from modules.shared.src.common.taxonomy_core_vo import MessageCount, ResponseText

_PAGINATION_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")


def partial_text_after_stream_cut(exc: BaseException, page: Page) -> str | None:
    """Partial assistant text for a run the monitor cut mid-stream (BE-1-003).

    Prefers the ``partial_text`` the stream monitor attached to
    ``StuckDetectedError`` / ``ResponseDetectionTimeoutError`` — the last
    forward-progress text this run confirmed — and falls back to reading the
    live DOM, which still holds a rendered partial answer when the cut fired
    before any forward event registered (e.g. a first-poll timeout on text
    that never differed from the baseline).

    Returns ``None`` when neither source has non-blank text: a stall before
    the first token legitimately has nothing to persist.
    """
    carried = getattr(exc, "partial_text", None)
    if isinstance(carried, str) and carried.strip():
        return carried.strip()
    try:
        dom_text = latest_message_text(page)
    except Exception:
        return None
    if isinstance(dom_text, str) and dom_text.strip():
        return dom_text.strip()
    return None


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


def count_user_messages(page: Page) -> int:
    """Count committed user turns via the user-bubble selectors.

    Qwen renders the user bubble (``.chat-user-message`` /
    ``.qwen-chat-message-user``) as soon as a turn is acknowledged,
    well before the assistant response streams in. This lets the
    dispatch-ACK stage detect a committed turn without waiting on the
    response surface.

    Returns
    -------
    int
        Number of user-turn elements, 0 when none or on error.

    """
    try:
        return int(page.locator(USER_COMBINED_SELECTOR).count())
    except Error:
        return 0


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
