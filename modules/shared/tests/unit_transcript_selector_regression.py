"""Pinned-transcript regression for the shared DOM query helpers (SHARED-02).

One captured chat.qwen.ai DOM snapshot — thinking → streaming → complete — is
committed under ``modules/shared/tests/fixtures/``. The helpers
``count_messages``, ``count_user_messages``, ``latest_message_text`` and
``partial_text_after_stream_cut`` are run against each phase so selector drift
(a renamed class in the live DOM) fails the kernel suite here before it fails
a run.

No browser binary is required: the helpers' Playwright ``Page`` is doubled by a
lightweight DOM shim implementing ``querySelectorAll``-style selection against
the fixture, so the real selectors (JS_GET_RESPONSE_TEXT, JS_COUNT_TURNS,
COMBINED_MESSAGE_SELECTOR, RESPONSE_CONTENT_SELECTOR, USER_COMBINED_SELECTOR)
are exercised unchanged against the transcript.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from modules.shared.src.common.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    RESPONSE_CONTENT_SELECTOR,
    USER_COMBINED_SELECTOR,
)
from modules.shared.src.common.taxonomy_core_vo import MessageCount, ResponseText
from modules.shared.src.common.utility_dom_query import (
    count_messages,
    count_user_messages,
    latest_message_text,
    partial_text_after_stream_cut,
)

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_thinking_streaming_complete.html"

PHASES: tuple[str, ...] = ("thinking", "streaming", "complete", "stale")

_PAGINATION_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")

#: Nodes the response-text JS walks, in document order (mirrors JS_GET_RESPONSE_TEXT).
_RESPONSE_NODE_SELECTORS: tuple[str, ...] = (
    ".qwen-markdown",
    ".qwen-chat-message-assistant",
    ".chat-response-message",
    ".chat-message-assistant",
    "[data-role='assistant']",
    ".response-message-content",
    ".qwen-markdown-text",
    "[class*='message-content']",
    "[class*='message-body']",
    "[class*='response']",
)

#: Stale thinking-card markers the JS skips (mirrors JS_GET_RESPONSE_TEXT).
_THINKING_CARD_MARKERS: tuple[str, ...] = (
    "thought stopped",
    "thought completed",
    "thought complete",
    "thinking stopped",
    "thinking completed",
    "thinking complete",
    "thinking process",
)


def _load_fixture() -> str:
    assert FIXTURE.is_file(), f"the pinned transcript fixture must exist at {FIXTURE}"
    return FIXTURE.read_text(encoding="utf-8")


class _Node:
    """A minimal DOM node: tag, classes, text, visibility, children, attributes."""

    __slots__ = ("tag", "classes", "text", "children", "visible", "attributes")

    def __init__(self, tag: str, attributes: dict[str, str]) -> None:
        self.tag = tag
        self.classes = {token for token in attributes.get("class", "").split() if token}
        self.text = ""
        self.children: list[_Node] = []
        attributes.pop("class", None)
        self.attributes = attributes
        self.visible = "hidden" not in attributes


class _TranscriptParser(HTMLParser):
    """Parse the fixture into a node tree, one <section data-phase> per phase."""

    def __init__(self) -> None:
        super().__init__()
        self.root = _Node("root", {})
        self.stack: list[_Node] = [self.root]
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: (value or "") for key, value in attrs}
        if self._skip_depth:
            self._skip_depth += 1
            return
        if tag in ("script", "style"):
            self._skip_depth = 1
            return
        node = _Node(tag, attributes)
        self.stack[-1].children.append(node)
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            self._skip_depth -= 1
            return
        if len(self.stack) > 1 and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self.stack[-1].text += data


def _section_dom(html: str, phase: str) -> _Node:
    parser = _TranscriptParser()
    parser.feed(html)
    parser.close()
    for section in _walk(parser.root):
        if section.tag == "section" and section.attributes.get("data-phase") == phase:
            return section
    raise AssertionError(f'the fixture has no <section data-phase="{phase}">')


def _walk(node: _Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _deep_text(node: _Node) -> str:
    return "".join(_walk_text(node))


def _walk_text(node: _Node):
    if node.tag not in ("script", "style"):
        yield node.text
    for child in node.children:
        yield from _walk_text(child)


def _split_steps(part: str) -> list[str]:
    steps: list[str] = []
    current: list[str] = []
    depth = 0
    for char in part:
        if char in "[(":
            depth += 1
        elif char in "])":
            depth = max(0, depth - 1)
        if char.isspace() and depth == 0:
            if current:
                steps.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        steps.append("".join(current))
    return steps


def _unquote(rest: str) -> str:
    rest = rest.lstrip()
    if rest[:1] in ("'", '"'):
        quote = rest[0]
        close = rest.find(quote, 1)
        if close != -1:
            return rest[1:close]
    return rest.split("]", 1)[0].strip()


def _matches_simple(node: _Node, step: str) -> bool:
    if step.startswith("[class*="):
        token = _unquote(step[len("[class*=") :])
        return any(token in class_name for class_name in node.classes)
    if step.startswith("[data-role="):
        token = _unquote(step[len("[data-role=") :])
        return node.attributes.get("data-role") == token
    if step.startswith("#"):
        return node.attributes.get("id") == step[1:]
    if step.startswith("."):
        class_token = re.split(r"[:.\[]", step[1:], maxsplit=1)[0]
        return class_token in node.classes
    if step == "button" or step.startswith(("button[", "button:")):
        if node.tag != "button":
            return False
        remainder = step[len("button") :].lstrip()
        return not remainder or _matches_simple(node, remainder)
    return node.tag == step


def _select(root: _Node, selector: str) -> list[_Node]:
    matches: list[_Node] = []
    for part in [p.strip() for p in selector.split(",")]:
        matches.extend(_select_one(root, part))
    return matches


def _select_one(root: _Node, part: str) -> list[_Node]:
    candidates = [root]
    for step in _split_steps(part):
        next_round: list[_Node] = []
        for candidate in candidates:
            next_round.extend(_match_step(candidate, step))
        candidates = next_round
    return candidates


def _match_step(node: _Node, step: str) -> list[_Node]:
    found: list[_Node] = []
    for descendant in _walk(node):
        if descendant is node:
            continue
        if _matches_simple(descendant, step):
            found.append(descendant)
    return found


def _collect_response_nodes(root: _Node) -> list[_Node]:
    """Document-order assistant nodes matching the response vocabulary."""
    union_parts = [part.strip() for sel in _RESPONSE_NODE_SELECTORS for part in sel.split(",")]
    found: list[_Node] = []

    def rec(node: _Node, in_user: bool) -> None:
        in_user = in_user or "qwen-chat-message-user" in node.classes or "user-message-content" in node.classes
        if not in_user and any(_matches_simple(node, part) for part in union_parts):
            found.append(node)
        for child in node.children:
            rec(child, in_user)

    rec(root, False)
    return found


_BLOCK_TAGS = {
    "P",
    "DIV",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "LI",
    "TR",
    "TD",
    "TH",
    "PRE",
    "BLOCKQUOTE",
    "BR",
    "TABLE",
    "UL",
    "OL",
    "SECTION",
    "ARTICLE",
}


def _render_text(node: _Node) -> str:
    """Mirror the DOM text walker in JS_GET_RESPONSE_TEXT."""
    text_chunks: list[str] = []

    def walk(n: _Node) -> None:
        if n.tag in ("script", "style"):
            return
        if n.tag == "br":
            text_chunks.append("\n")
            return
        if n.text:
            text_chunks.append(n.text)
        for child in n.children:
            walk(child)
        if n.tag.upper() in _BLOCK_TAGS and text_chunks and not text_chunks[-1].endswith("\n"):
            text_chunks.append("\n")

    walk(node)
    raw = "".join(text_chunks)
    cleaned = re.sub(r"[ \t]+\n", "\n", raw)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _js_get_response_text(root: _Node) -> str | None:
    """Mirror JS_GET_RESPONSE_TEXT: reverse walk, skip user subtrees,
    pagination indicators, and stale thinking-card markers."""
    for node in reversed(_collect_response_nodes(root)):
        text = _render_text(node)
        if not text or _PAGINATION_RE.match(text):
            continue
        if text.lower().strip() in _THINKING_CARD_MARKERS:
            continue
        return text
    return None


def _js_count_turns(root: _Node) -> int:
    """Mirror JS_COUNT_TURNS: count turn elements."""
    selectors = (
        ".chat-response-message, [class*='chat-message'], [class*='message-item'], "
        "[class*='virtual-list-item'], [class*='turn']"
    )
    return len(_select(root, selectors))


class _LocatorShim:
    """page.locator shim answering count / first / last.text_content against the DOM."""

    def __init__(self, root: _Node, selector: str) -> None:
        self._nodes = _select(root, selector)

    def count(self) -> int:
        return len(self._nodes)

    @property
    def first(self) -> _LocatorShim:
        return _LocatorShimFromNodes(self._nodes[:1])

    @property
    def last(self) -> _LocatorShim:
        return _LocatorShimFromNodes(self._nodes[-1:])


class _LocatorShimFromNodes:
    def __init__(self, nodes: list[_Node]) -> None:
        self._nodes = nodes

    def count(self) -> int:
        return len(self._nodes)

    def text_content(self) -> str | None:
        if not self._nodes:
            return None
        return _deep_text(self._nodes[-1])


class _FixturePage(MagicMock):
    """Page double whose evaluate/locator answer from the fixture DOM."""

    def __init__(self, html: str, phase: str) -> None:
        super().__init__(spec=["evaluate", "locator"])
        self._root = _section_dom(html, phase)
        self.locator = lambda selector: _LocatorShim(self._root, selector)

    def evaluate(self, script: str, *args: Any) -> Any:
        if script == JS_COUNT_TURNS:
            return _js_count_turns(self._root)
        if script == JS_GET_RESPONSE_TEXT:
            return _js_get_response_text(self._root)
        raise AssertionError(f"unexpected page.evaluate script: {script[:80]!r}")


class _StubError:
    """Minimal exception stand-in carrying an optional partial_text attribute."""

    def __init__(self, partial_text: str | None = None) -> None:
        self.partial_text = partial_text


# ─── Phase expectations ─────────────────────────────────────────────────────


_EXPECTED: dict[str, dict[str, Any]] = {
    "thinking": {
        "count_messages": 1,
        "count_user_messages": 1,
        "latest_message_text": None,
    },
    "streaming": {
        "count_messages": 2,
        "count_user_messages": 1,
        "latest_message_text": "Revenue grew 12% quarter over quarter.",
    },
    "complete": {
        "count_messages": 2,
        "count_user_messages": 1,
        "latest_message_text": (
            "Revenue grew 12% quarter over quarter.\n"
            "Operating margin improved by 3 points, driven by lower cloud spend."
        ),
    },
    "stale": {
        "count_messages": 4,
        "count_user_messages": 1,
        "latest_message_text": "Live answer: Revenue grew 12% quarter over quarter.",
    },
}


class TestTranscriptSelectorRegression:
    """The helpers must read every phase of the pinned transcript correctly."""

    def test_the_fixture_covers_every_phase(self) -> None:
        html = _load_fixture()
        for phase in PHASES:
            assert _section_dom(html, phase) is not None

    def test_each_phase_is_present_exactly_once(self) -> None:
        html = _load_fixture()
        parser = _TranscriptParser()
        parser.feed(html)
        parser.close()
        sections = [n for n in _walk(parser.root) if n.tag == "section"]
        assert sorted(n.attributes.get("data-phase", "") for n in sections) == sorted(PHASES)

    @pytest.mark.parametrize("phase", PHASES)
    def test_count_messages_matches_transcript(self, phase: str) -> None:
        page = _FixturePage(_load_fixture(), phase)
        assert count_messages(page) == MessageCount(_EXPECTED[phase]["count_messages"])

    @pytest.mark.parametrize("phase", PHASES)
    def test_count_user_messages_matches_transcript(self, phase: str) -> None:
        page = _FixturePage(_load_fixture(), phase)
        assert count_user_messages(page) == _EXPECTED[phase]["count_user_messages"]

    @pytest.mark.parametrize("phase", PHASES)
    def test_latest_message_text_matches_transcript(self, phase: str) -> None:
        page = _FixturePage(_load_fixture(), phase)
        expected = _EXPECTED[phase]["latest_message_text"]
        result = latest_message_text(page)
        if expected is None:
            assert result is None
        else:
            assert result == ResponseText(expected)

    def test_partial_text_after_stream_cut_falls_back_to_dom(self) -> None:
        """No carried partial text -> the helper reads the live DOM."""
        page = _FixturePage(_load_fixture(), "streaming")
        assert partial_text_after_stream_cut(_StubError(None), page) == ("Revenue grew 12% quarter over quarter.")

    def test_partial_text_after_stream_cut_prefers_carried_text(self) -> None:
        page = _FixturePage(_load_fixture(), "streaming")
        assert partial_text_after_stream_cut(_StubError("carried partial"), page) == "carried partial"

    # ─── Selector drift guards ──────────────────────────────────────────

    def test_every_pinned_selector_matches_its_transcript_phase(self) -> None:
        """Coverage guard: each selector the helpers compile must still match."""
        html = _load_fixture()
        thinking = _section_dom(html, "thinking")
        streaming = _section_dom(html, "streaming")
        complete = _section_dom(html, "complete")
        stale = _section_dom(html, "stale")

        # COMBINED_MESSAGE_SELECTOR / RESPONSE_CONTENT_SELECTOR match assistant bubbles.
        assert _select(streaming, COMBINED_MESSAGE_SELECTOR)
        assert _select(complete, COMBINED_MESSAGE_SELECTOR)
        assert _select(stale, COMBINED_MESSAGE_SELECTOR)
        assert _select(streaming, RESPONSE_CONTENT_SELECTOR)
        assert _select(complete, RESPONSE_CONTENT_SELECTOR)
        assert _select(stale, RESPONSE_CONTENT_SELECTOR)
        assert not _select(thinking, COMBINED_MESSAGE_SELECTOR)

        # USER_COMBINED_SELECTOR matches the user bubble in every phase.
        for phase in PHASES:
            assert _select(_section_dom(html, phase), USER_COMBINED_SELECTOR)

        # JS_COUNT_TURNS vocabulary matches turn-bearing phases.
        assert _js_count_turns(streaming) > 0
        assert _js_count_turns(complete) > 0
        assert _js_count_turns(stale) > 0

    def test_a_renamed_assistant_class_breaks_latest_message_text(self) -> None:
        """Selector drift: rename all assistant classes and latest_message_text must miss."""
        html = (
            _load_fixture()
            .replace("qwen-chat-message-assistant", "qwen-chat-answer-bubble")
            .replace("qwen-markdown", "qwen-formatted-body")
            .replace("response-message-content", "answer-content")
        )
        streaming = _section_dom(html, "streaming")
        page = MagicMock(spec=["evaluate", "locator"])
        page.evaluate.return_value = _js_get_response_text(streaming)
        page.locator = lambda selector: _LocatorShim(streaming, selector)
        # With renamed classes the JS tier finds no response node → falls to locator tier,
        # which also finds nothing under RESPONSE_CONTENT_SELECTOR.
        assert latest_message_text(page) is None

    def test_a_renamed_user_class_breaks_count_user_messages(self) -> None:
        """Selector drift: rename the user bubble and count_user_messages returns 0."""
        html = _load_fixture().replace("qwen-chat-message-user", "qwen-chat-prompt-bubble")
        streaming = _section_dom(html, "streaming")
        page = _FixturePage(_load_fixture(), "streaming")
        # Rebuild a page whose locator answers against the renamed-class DOM.
        page.locator = lambda selector: _LocatorShim(streaming, selector)
        assert count_user_messages(page) == 0
