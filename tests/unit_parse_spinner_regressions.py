"""Regression tests: spinner visibility must gate parse-wait and send-gate.

Bug: Qwen's ``.anticon-spin.fileitem-loading-icon`` SVG is always present in
the file-card DOM after parsing completes (hidden via CSS). Both the
uploader's ``_wait_for_dom_parse_ready`` and the dispatcher's
``_is_file_card_parsing`` previously counted DOM elements without verifying
visibility, so the send button stayed disabled indefinitely and the
lifecycle gate rejected ``EVENT_PROMPT_INJECTED`` because
``EVENT_DOCUMENT_PARSED`` was never emitted.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.core.src import capabilities_send_dispatcher as sd
from modules.core.src.capabilities_file_uploader import FileUploader

# ── Precise DOM mock ─────────────────────────────────────────────────────────


def _build_page(
    card_text: str = "attachment\n.md\n310.0 B",
    spinner_visible: bool = False,
    spinner_count: int = 2,
    toast_text: str = "",
) -> MagicMock:
    """Return a Page mock whose locators mimic the real Qwen file-card DOM.

    - ``.message-input-column-file`` (and the other narrow card selectors)
      resolves to a card whose ``inner_text`` is *card_text*.
    - Inside that card, spinner selectors resolve to *spinner_count*
      elements, each with ``is_visible() == spinner_visible``.
    - Toast selectors resolve to a single element whose text is *toast_text*.

    ``cards.last`` returns the same locator (Playwright semantics: the
    ``last`` property of a filtered locator is the locator itself when a
    single match is expected).
    """
    page = MagicMock()

    card_elem = MagicMock()
    card_elem.is_visible.return_value = True
    card_elem.inner_text.return_value = card_text
    card_elem.count.return_value = 1

    spinner_elems: list[MagicMock] = []
    for _ in range(spinner_count):
        sp = MagicMock()
        sp.is_visible.return_value = spinner_visible
        spinner_elems.append(sp)

    def spinner_locator() -> MagicMock:
        loc = MagicMock()
        loc.count.return_value = spinner_count
        for i in range(spinner_count):
            loc.nth.return_value = spinner_elems[i]
        loc.first = spinner_elems[0] if spinner_count else MagicMock()
        return loc

    def card_locator_factory(sel: str) -> MagicMock:
        sel_l = sel.lower()
        # Spinner and pending-loading selectors all resolve to the spinner elements
        if any(k in sel_l for k in ("spin", "loading", "parsing")):
            return spinner_locator()
        return MagicMock(count=MagicMock(return_value=0))

    card_elem.locator.side_effect = card_locator_factory
    # Playwright: filtered.last returns the filtered locator when count==1
    card_elem.last = card_elem

    toast_elem = MagicMock()
    toast_elem.is_visible.return_value = bool(toast_text)
    toast_elem.inner_text.return_value = toast_text

    def page_locator_factory(sel: str) -> MagicMock:
        sel_l = sel.lower()
        # Narrow card selectors all resolve to the same card element
        if any(k in sel_l for k in (
            "message-input-column-file",
            "file-card-list",
            "fileitem",
            "file-card",
            "file-item",
            "attachment",
        )):
            loc = MagicMock()
            loc.count.return_value = 1
            loc.nth.return_value = card_elem
            loc.first = card_elem
            loc.last = card_elem
            loc.filter.return_value = card_elem
            return loc
        # Toast selectors
        if any(k in sel_l for k in ("ant-message", "toast", "notification", "alert", "body")):
            loc = MagicMock()
            loc.count.return_value = 1 if toast_text else 0
            loc.nth.return_value = toast_elem
            loc.first = toast_elem
            return loc
        return MagicMock(count=MagicMock(return_value=0), nth=MagicMock(return_value=MagicMock()))

    page.locator.side_effect = page_locator_factory
    page.wait_for_timeout = MagicMock()
    return page


# ── _is_file_card_parsing ─────────────────────────────────────────────────────


class TestIsFileCardParsingSpinnerVisibility:
    """_is_file_card_parsing must return False when spinners are hidden."""

    def test_hidden_spinners_return_false(self):
        page = _build_page(card_text="attachment\n.md\n310.0 B", spinner_visible=False, spinner_count=2)
        assert sd._is_file_card_parsing(page) is False

    def test_visible_spinner_returns_true(self):
        page = _build_page(card_text="attachment\n.md\n310.0 B", spinner_visible=True, spinner_count=2)
        assert sd._is_file_card_parsing(page) is True

    def test_parsing_keyword_in_card_text_returns_true(self):
        page = _build_page(card_text="attachment currently parsing…", spinner_visible=False)
        assert sd._is_file_card_parsing(page) is True

    def test_processing_keyword_in_card_text_returns_true(self):
        page = _build_page(card_text="attachment processing file…", spinner_visible=False)
        assert sd._is_file_card_parsing(page) is True

    def test_no_spinners_no_keywords_returns_false(self):
        page = _build_page(card_text="attachment\n.md\n310.0 B", spinner_visible=False, spinner_count=0)
        assert sd._is_file_card_parsing(page) is False

    def test_broad_container_selectors_excluded(self):
        # The dispatcher must not consult [class*='composer'] or [class*='input']
        # because those match container divs, not the file card itself.
        import inspect
        src = inspect.getsource(sd._is_file_card_parsing)
        assert "[class*='composer']" not in src
        assert "[class*='input']" not in src


# ── _wait_for_send_enabled hold_on_card_parsing flag ─────────────────────────


class TestWaitForSendEnabledHoldFlag:
    """When hold_on_card_parsing=False, the card spinner must not block the send."""

    def test_no_hold_when_document_parsed(self):
        from modules.core.src.capabilities_send_dispatcher import SendDispatcher

        dispatcher = SendDispatcher()
        call_log: list[bool] = []

        def fake_parsing(page_: MagicMock) -> bool:
            call_log.append(True)
            return True  # simulate: card spinner is still visible

        # With hold_on_card_parsing=False the parsing check must be skipped,
        # so _wait_for_send_enabled returns as soon as the send button is enabled.
        page = _build_page(card_text="attachment\n.md", spinner_visible=True)
        with patch.object(sd, "_is_file_card_parsing", side_effect=fake_parsing), \
             patch.object(sd, "_is_parse_toast_visible", return_value=False):
            dispatcher._wait_for_send_enabled(page, timeout_ms=500, hold_on_card_parsing=False)
        assert call_log == [], f"_is_file_card_parsing called with hold=False: {call_log}"

    def test_hold_when_not_parsed(self):
        from modules.core.src.capabilities_send_dispatcher import SendDispatcher

        dispatcher = SendDispatcher()
        call_log: list[bool] = []

        def fake_parsing(page_: MagicMock) -> bool:
            call_log.append(True)
            return True  # card spinner still visible → keep holding

        page = _build_page(card_text="attachment\n.md", spinner_visible=True)
        with patch.object(sd, "_is_file_card_parsing", side_effect=fake_parsing), \
             patch.object(sd, "_is_parse_toast_visible", return_value=False):
            # hold=True and spinner visible → the send is held; the deadline
            # (500ms) elapses and the method returns False.
            result = dispatcher._wait_for_send_enabled(page, timeout_ms=500, hold_on_card_parsing=True)
            assert result is False
            assert len(call_log) >= 1, "parsing check was not consulted with hold=True"


# ── _wait_for_dom_parse_ready ─────────────────────────────────────────────────


class TestWaitForDomParseReadySpinnerVisibility:
    """_wait_for_dom_parse_ready must exit when only hidden spinners remain."""

    def test_hidden_spinners_complete(self, tmp_path):
        filepath = tmp_path / "test.md"
        filepath.write_text("hello")
        page = _build_page(card_text="test\n.md\n5.0 B", spinner_visible=False, spinner_count=2)

        with patch("modules.core.src.capabilities_file_uploader.time") as mod_time:
            # Call 1 (deadline base) → 0.0; call 2 (while check) → 0.0 (< 0.001, body
            # runs); subsequent calls → 99999.0 (past deadline, loop exits if the
            # body did not return).
            mod_time.monotonic.side_effect = [0.0, 0.0, 99999.0, 99999.0, 99999.0, 99999.0]
            mod_time.sleep = lambda s: None
            uploader = FileUploader()
            uploader.parse_ready_timeout_ms = 1  # deadline = 0 + 0.001s

            # The loop body runs once, finds is_ready=True, and returns.
            uploader._wait_for_dom_parse_ready(page, filepath)
            # No exception = success

    def test_visible_spinners_time_out(self, tmp_path):
        filepath = tmp_path / "test.md"
        filepath.write_text("hello")
        page = _build_page(card_text="test\n.md\n5.0 B", spinner_visible=True, spinner_count=2)

        with patch("modules.core.src.capabilities_file_uploader.time") as mod_time:
            # The loop runs one iteration: deadline = 0.0 + 0.001, while check at 0.0
            # enters the body. The visible spinner makes is_ready False, so the body
            # falls through to wait_for_timeout(300) and loops back; the third
            # monotonic call returns 99999.0 which exceeds the deadline → exit.
            mod_time.monotonic.side_effect = [0.0, 0.0, 99999.0, 99999.0, 99999.0]
            mod_time.sleep = lambda s: None
            uploader = FileUploader()
            uploader.parse_ready_timeout_ms = 1  # deadline = 0 + 0.001s

            with pytest.raises(TimeoutError, match="did not reach ready state"):
                uploader._wait_for_dom_parse_ready(page, filepath)
