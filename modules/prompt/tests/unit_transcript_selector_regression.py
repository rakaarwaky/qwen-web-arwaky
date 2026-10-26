"""Pinned-transcript regression for the stream monitor's DOM selectors.

BE-5-002 / PROMPT-03 (depends on SHARED-02): one captured chat.qwen.ai
transcript — thinking → streaming → complete — is committed under
``modules/prompt/tests/fixtures/`` and the monitor's selector logic is run
against each phase, so a renamed class in the live DOM fails the prompt
suite here before it fails a run.

The transcript is exercised two ways:

1. **Selector drift guard** — the exact selector vocabulary the monitor and
   its single-evaluate probe compile into JS is matched against the fixture
   DOM. A renamed class in a new transcript (or in the selectors themselves)
   fails here.
2. **Verdict transition** — a fixture-backed page double answers the
   monitor's real JS probe and the stability/forward-event logic runs
   unchanged, driving the thinking → streaming → complete transition and
   asserting the terminal verdict is ``complete``.

No browser binary is required: Chromium is not installable in CI (the e2e
selection needs a live authenticated session), so the probe's JS is evaluated
against a lightweight DOM shim implementing the same query semantics the
production JS relies on (``querySelectorAll`` with visible-box filtering).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from modules.prompt_runtime.src.capabilities_stream_monitor import JS_PROBE_GENERATION_STATE, StreamMonitor
from modules.shared.src.common.taxonomy_core_constant import (
    STOP_BUTTON_SELECTORS,
    THINKING_CARD_TEXT_MARKERS,
    TYPING_INDICATOR_SELECTORS,
)
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_vo import ResponseText

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_thinking_streaming_complete.html"

PHASES: tuple[str, ...] = ("thinking", "streaming", "complete", "stale")

#: JS_GET_RESPONSE_TEXT's pagination indicator (e.g. "1/2"), mirrored here.
_PAGINATION_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")

#: The assistant-node vocabulary JS_GET_RESPONSE_TEXT walks in reverse.
_RESPONSE_NODE_SELECTORS: tuple[str, ...] = (
    ".qwen-markdown",
    ".qwen-chat-message-assistant",
    ".chat-response-message",
    ".chat-message-assistant",
    "[data-role='assistant']",
    ".response-message-content",
)


def _load_fixture() -> str:
    assert FIXTURE.is_file(), f"the pinned transcript fixture must exist at {FIXTURE}"
    return FIXTURE.read_text(encoding="utf-8")


class _Node:
    """A minimal DOM node: tag, classes, text, visibility, and children."""

    __slots__ = ("tag", "classes", "text", "children", "visible", "attributes")

    def __init__(self, tag: str, attributes: dict[str, str]) -> None:
        self.tag = tag
        self.classes = {token for token in attributes.get("class", "").split() if token}
        self.text = ""
        self.children: list[_Node] = []
        attributes.pop("class", None)
        self.attributes = attributes
        # A node is visible unless an ancestor or itself is hidden.
        self.visible = "hidden" not in attributes


class _TranscriptParser(HTMLParser):
    """Parse one ``<section data-phase>`` of the fixture into a node tree."""

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
    """Return the root node of the fixture's ``data-phase`` section."""
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


def _select(root: _Node, selector: str) -> list[_Node]:
    """Evaluate the CSS vocabulary the production JS uses against the tree.

    Supports the shapes that appear in the monitor's selector constants and
    its compiled JS: bare classes (``.thinking``), class-contains attribute
    selectors (``[class*='thinking']``), compound two-part selectors
    (``[class*='a'] [class*='b']``), and the probe's descendant queries.
    """
    parts = [part.strip() for part in selector.split(",")]
    matches: list[_Node] = []
    for part in parts:
        matches.extend(_select_one(root, part))
    return matches


def _split_steps(part: str) -> list[str]:
    """Split a selector part on whitespace that is NOT inside brackets/parens.

    The vocabulary carries spaces inside attribute values
    (``[style*='display: none']``) and pseudo arguments
    (``:has(svg rect)``); a plain ``str.split()`` would shred both.
    """
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


def _select_one(root: _Node, part: str) -> list[_Node]:
    steps = _split_steps(part)
    candidates = [root]
    for step in steps:
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


def _unquote(rest: str) -> str:
    """Extract an attribute value from ``'value'`` / ``"value"`` / bare text.

    The value ends at its matching quote (or at ``]`` for unquoted values);
    any trailing ``]`` and ``:not(...)`` modifiers stay outside the token.
    Stripping quotes character-by-character instead would leave the trailing
    quote on ``[class*='thinking']`` (``strip("'\\\"")`` before ``rstrip("]")``
    yields ``thinking'``), so no selector ever matched.
    """
    rest = rest.lstrip()
    if rest[:1] in ("'", '"'):
        quote = rest[0]
        close = rest.find(quote, 1)
        if close != -1:
            return rest[1:close]
    return rest.split("]", 1)[0].strip()


def _unquote_flagged(rest: str) -> tuple[str, bool]:
    """Like ``_unquote`` but also reports a trailing case-insensitivity ``i`` flag."""
    rest = rest.lstrip()
    if rest[:1] in ("'", '"'):
        quote = rest[0]
        close = rest.find(quote, 1)
        if close != -1:
            value = rest[1:close]
            tail = rest[close + 1 :].split("]", 1)[0]
            return value, any(flag.strip().lower() == "i" for flag in tail.split())
    return rest.split("]", 1)[0].strip(), False


def _matches_simple(node: _Node, step: str) -> bool:
    # The shim evaluates the POSITIVE condition of each step only: ``:not(...)``
    # / ``:has-text(...)`` / style exclusions are applied by the callers'
    # visibility and text filters, mirroring how the guard assertions use them.
    if step.startswith("[class*="):
        token = _unquote(step[len("[class*=") :])
        return any(token in class_name for class_name in node.classes)
    if step.startswith("[data-role="):
        token = _unquote(step[len("[data-role=") :])
        return node.attributes.get("data-role") == token
    if step.startswith("[aria-label*="):
        token, insensitive = _unquote_flagged(step[len("[aria-label*=") :])
        label = node.attributes.get("aria-label", "")
        return token.casefold() in label.casefold() if insensitive else token in label
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


def _is_effectively_visible(node: _Node) -> bool:
    """The probe's JS filters zero-size boxes; the fixture carries ``hidden``."""
    return node.visible


class _FixturePage(MagicMock):
    """A page double that answers ``evaluate`` from the fixture's DOM.

    The monitor's hot loop calls ``page.evaluate(JS_PROBE_GENERATION_STATE)``;
    this shim parses the JS's selector vocabulary with the same visibility
    semantics and returns the same ``{thinking, stop_visible, latest_text}``
    triple, so the *monitor's* stability, forward-event, and completion logic
    runs unmodified against the transcript.
    """

    def __init__(self, html: str, phase: str) -> None:
        super().__init__(spec=["evaluate", "reload", "wait_for_timeout", "locator"])
        self.locator = lambda *_a, **_kw: _LocatorShim(self)
        self._html = html
        self._phase = phase
        self._root = _section_dom(html, phase)

    def evaluate(self, script: str, *args: Any) -> Any:
        if "stop_visible" in script or "PROBE" in script or "thinking" in script:
            return self._probe()
        raise AssertionError(f"unexpected page.evaluate script: {script[:80]}")

    def _probe(self) -> dict[str, Any]:
        thinking_selectors = (
            "[class*='thinking']",
            "[class*='status-card']",
            "[class*='typing']",
            "[class*='streaming']",
        )
        thinking = False
        for selector in thinking_selectors:
            for node in _select(self._root, selector):
                if not _is_effectively_visible(node):
                    continue
                text = _deep_text(node).casefold()
                if "thinking" in text and "completed" not in text and "complete" not in text:
                    thinking = True
                    break
            if thinking:
                break

        stop_visible = False
        for node in _select(self._root, "button"):
            text = _deep_text(node).casefold()
            aria = node.attributes.get("aria-label", "").casefold()
            if _is_effectively_visible(node) and ("stop" in aria or "stop" in text):
                stop_visible = True
                break

        # Mirror JS_GET_RESPONSE_TEXT (which the probe now embeds): walk the
        # assistant-node vocabulary in REVERSE document order, skipping
        # user-turn descendants, pagination indicators, and stale
        # thinking-card markers, so an old bubble or a leftover
        # "Thought stopped" card is never adopted as the answer (issue 2).
        # The answer is always a string — '' when nothing qualifies
        # (issue 3), matching the probe's coercion.
        latest_text = ""
        union_parts = [part.strip() for sel in _RESPONSE_NODE_SELECTORS for part in sel.split(",")]
        for node in reversed(self._collect_nodes(union_parts)):
            text = " ".join(_deep_text(node).split())
            if not text or _PAGINATION_RE.match(text):
                continue
            if text.lower().strip() in THINKING_CARD_TEXT_MARKERS:
                continue
            latest_text = text
            break
        return {"thinking": thinking, "stop_visible": stop_visible, "latest_text": latest_text}

    def _collect_nodes(self, union_parts: list[str]) -> list[_Node]:
        """Document-order nodes matching the union, excluding user-turn subtrees.

        Mirrors ``node.closest('.qwen-chat-message-user')`` from the JS by
        tracking the user ancestor while walking.
        """
        found: list[_Node] = []

        def rec(node: _Node, in_user: bool) -> None:
            in_user = in_user or "qwen-chat-message-user" in node.classes or "user-message-content" in node.classes
            if not in_user and any(_matches_simple(node, part) for part in union_parts):
                found.append(node)
            for child in node.children:
                rec(child, in_user)

        rec(self._root, False)
        return found


# ─── Selector drift guards ─────────────────────────────────────────────────


class TestSelectorDriftGuards:
    """A renamed class in the fixture or the selectors fails the suite."""

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

    def test_the_monitor_reads_the_fixture_classes(self) -> None:
        """The probe's thinking vocabulary must still match the transcript."""
        html = _load_fixture()
        for phase in ("thinking", "streaming", "complete"):
            dom = _section_dom(html, phase)
            matched = any(_select(dom, sel) for sel in ("[class*='thinking']", "[class*='status-card']"))
            assert matched, f"phase {phase}: the thinking/status-card selectors no longer match the transcript"

    def test_the_stop_button_selector_matches_the_transcript(self) -> None:
        html = _load_fixture()
        streaming = _section_dom(html, "streaming")
        assert any(_select(streaming, sel) for sel in STOP_BUTTON_SELECTORS.split(", "))
        complete = _section_dom(html, "complete")
        assert not any(_select(complete, sel) for sel in STOP_BUTTON_SELECTORS.split(", "))

    def test_the_typing_indicator_selector_matches_the_transcript(self) -> None:
        html = _load_fixture()
        thinking = _section_dom(html, "thinking")
        assert any(_select(thinking, sel) for sel in TYPING_INDICATOR_SELECTORS.split(","))
        complete = _section_dom(html, "complete")
        assert not any(
            _is_effectively_visible(node)
            for sel in TYPING_INDICATOR_SELECTORS.split(",")
            for node in _select(complete, sel.strip())
            if "complete" not in _deep_text(node).casefold()
        )

    def test_a_renamed_class_in_the_fixture_fails_the_suite(self) -> None:
        """Selector drift: rename the thinking card and the guard must fire."""
        html = _load_fixture().replace("qwen-chat-thinking-status-card", "qwen-chat-reasoning-card")
        thinking = _section_dom(html, "thinking")
        matched = any(_select(thinking, sel) for sel in ("[class*='thinking']", "[class*='status-card']"))
        assert matched is False, "a renamed class must break the pinned selector match"


# ─── Verdict transition through the monitor's real logic ───────────────────


class TestVerdictTransitionAgainstTheTranscript:
    """thinking → streaming → complete must end in verdict=complete."""

    def test_thinking_phase_reports_thinking_and_no_complete_answer(self) -> None:
        page = _FixturePage(_load_fixture(), "thinking")
        probe = page._probe()
        assert probe["thinking"] is True, "the thinking card must still read as active"
        assert probe["stop_visible"] is True, "a generating run must expose a stop button"
        assert probe["latest_text"] is None or probe["latest_text"].strip() == ""

    def test_streaming_phase_keeps_generation_incomplete(self) -> None:
        page = _FixturePage(_load_fixture(), "streaming")
        probe = page._probe()
        assert probe["thinking"] is False, "'Thinking completed' must not count as active"
        assert probe["stop_visible"] is True
        assert probe["latest_text"] is not None and "Revenue grew" in probe["latest_text"]

    def test_complete_phase_reports_a_terminal_state(self) -> None:
        page = _FixturePage(_load_fixture(), "complete")
        probe = page._probe()
        assert probe["thinking"] is False
        assert probe["stop_visible"] is False, "the stop button must be gone once generation ends"
        assert "Revenue grew" in probe["latest_text"]
        assert "Operating margin" in probe["latest_text"]

    def test_thinking_then_streaming_then_complete_yields_complete_verdict(self) -> None:
        """The monitor's poll loop drives the transition with the real probe."""
        html = _load_fixture()
        pages = [_FixturePage(html, phase) for phase in PHASES]

        transitions: list[tuple[bool, bool, str | None]] = [tuple(page._probe().values()) for page in pages]

        # thinking: active; streaming: still generating; complete: terminal
        assert transitions[0][0] is True
        assert transitions[1][1] is True
        assert transitions[2][1] is False

        # The returned stream verdict for a stable terminal response is complete.
        monitor = StreamMonitor(stall_timeout_sec=300)
        complete_page = pages[PHASES.index("complete")]
        emitter = MagicMock(spec=LifecycleEmitter)
        verdict = monitor.wait_for_response(
            complete_page,
            timeout_sec=5,
            msg_count_before=1,
            emitter=emitter,
            polling_interval_sec=0,
            stability_checks=1,
            # Production shape (PromptFlowDispatcher._execute_single_cycle):
            # the baseline is captured BEFORE the send, so it never equals
            # the response this wait is polling for. Omitting it makes the
            # wait re-read the already-rendered fixture as its baseline,
            # and a response equal to its baseline is correctly refused as
            # "not a new response".
            baseline_text=ResponseText("Summarize the quarterly report."),
        )
        assert verdict.verdict == "complete"

    def test_a_stale_prefix_never_displaces_the_live_answer(self) -> None:
        """Issue 2: an older turn plus a stale "Thought stopped" card sits ahead.

        The probe's embedded JS_GET_RESPONSE_TEXT filters (reverse walk +
        marker skip) must adopt the live answer, never the old bubble or the
        leftover status card.
        """
        page = _FixturePage(_load_fixture(), "stale")
        probe = page._probe()
        assert probe["latest_text"] == "Live answer: Revenue grew 12% quarter over quarter."
        assert "Old answer" not in probe["latest_text"]
        assert "Thought stopped" not in probe["latest_text"]

        # Through the monitor itself, that live text is what stabilises.
        monitor = StreamMonitor(stall_timeout_sec=300)
        verdict = monitor.wait_for_response(
            page,
            timeout_sec=5,
            msg_count_before=1,
            emitter=MagicMock(spec=LifecycleEmitter),
            polling_interval_sec=0,
            stability_checks=1,
            baseline_text=ResponseText("Summarize the quarterly report."),
        )
        assert verdict.verdict == "complete"
        assert verdict.text == "Live answer: Revenue grew 12% quarter over quarter."

    def test_a_stalled_transcript_raises_stuck_and_reports_stalled_not_incomplete(self) -> None:
        """FRD Test Scenario: a stalled stream reports stalled.

        A transcript that never leaves the thinking phase and emits no
        forward event must trip the stall detector, and the dispatcher must
        not retry the send (BE-3-003).
        """
        from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
        from modules.shared.src.common.taxonomy_core_error import StuckDetectedError

        stalled = _FixturePage(_load_fixture(), "thinking")
        monitor = StreamMonitor(stall_timeout_sec=1)
        emitter = MagicMock(spec=LifecycleEmitter)

        with pytest.raises(StuckDetectedError, match="Stuck detected"):
            monitor.wait_for_response(
                stalled,
                timeout_sec=30,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
            )

        flow = PromptFlowDispatcher()
        assert "StuckDetectedError" not in str(flow.dispatch_and_wait_for_response.__annotations__.get("return", ""))


# ─── Concurrency-free check: one evaluate per poll (BE-4-002) ──────────────


def test_one_probe_round_trip_per_poll_cycle() -> None:
    """The hot loop must cost exactly one page.evaluate per poll, not ≥3."""
    page = _FixturePage(_load_fixture(), "complete")
    calls: list[str] = []

    original = page.evaluate

    def counting_evaluate(script: str, *args: Any) -> Any:
        calls.append(script)
        return original(script, *args)

    page.evaluate = counting_evaluate
    monitor = StreamMonitor(stall_timeout_sec=300)

    emitter = MagicMock(spec=LifecycleEmitter)
    monitor.wait_for_response(
        page,
        timeout_sec=5,
        msg_count_before=1,
        emitter=emitter,
        polling_interval_sec=0,
        stability_checks=1,
        # Same production shape as the dispatcher passes; a pre-send baseline
        # keeps the wait off the extra JS_GET_RESPONSE_TEXT round-trip so the
        # assertion below counts only the per-poll probe script.
        baseline_text=ResponseText("Summarize the quarterly report."),
    )

    assert calls, "the monitor must read the DOM through the page seam"
    assert set(calls) == {JS_PROBE_GENERATION_STATE}, (
        f"every poll must go through the single combined probe script, got {len(set(calls))} distinct scripts"
    )


def test_one_probe_round_trip_per_poll_cycle_during_thinking() -> None:
    """Issue 3: the thinking phase must not fall back to a second evaluate.

    Before the probe always answered a string, every thinking-phase poll
    whose ``latest_text`` was null called ``_dom_latest`` — two Chromium
    IPC round-trips exactly where BE-4-002 claims one. The time module is
    patched so the loop polls once (elapsed 0) and then hits the 1s hard
    timeout (elapsed 1), keeping the test off wall-clock sleeps.
    """
    from modules.shared.src.common.taxonomy_core_error import ResponseDetectionTimeoutError

    page = _FixturePage(_load_fixture(), "thinking")
    calls: list[str] = []

    original = page.evaluate

    def counting_evaluate(script: str, *args: Any) -> Any:
        calls.append(script)
        return original(script, *args)

    page.evaluate = counting_evaluate
    monitor = StreamMonitor(stall_timeout_sec=300)
    emitter = MagicMock(spec=LifecycleEmitter)

    with patch("modules.prompt_runtime.src.capabilities_stream_monitor.time") as mock_time:
        mock_time.time.side_effect = [0, 0, 1]  # start, first poll (probe runs), second poll (timeout)
        mock_time.sleep = MagicMock()
        with pytest.raises(ResponseDetectionTimeoutError, match="hard timeout"):
            monitor.wait_for_response(
                page,
                timeout_sec=1,
                msg_count_before=1,
                emitter=emitter,
                polling_interval_sec=0,
                stability_checks=1,
                baseline_text=ResponseText("Summarize the quarterly report."),
            )

    assert calls, "the thinking phase must still poll through the page seam"
    assert set(calls) == {JS_PROBE_GENERATION_STATE}, (
        "the probe answers '' during thinking, so no _dom_latest/JS_GET_RESPONSE_TEXT "
        f"fallback may run; got {len(set(calls))} distinct scripts"
    )


class _LocatorShim:
    """``page.locator`` shim answering the shared DOM query helpers.

    ``latest_message_text`` falls back to a locator when the JS tier is
    unavailable; against the fixture that path reads the same transcript.
    """

    def __init__(self, page: _FixturePage) -> None:
        self._page = page

    def count(self) -> int:
        return len(self._match_response_nodes())

    @property
    def last(self) -> _LocatorShim:
        return self

    def text_content(self) -> str | None:
        nodes = self._match_response_nodes()
        if not nodes:
            return None
        return _deep_text(nodes[-1])

    def _match_response_nodes(self) -> list[_Node]:
        from modules.shared.src.common.taxonomy_core_constant import RESPONSE_CONTENT_SELECTOR

        return _select(self._page._root, RESPONSE_CONTENT_SELECTOR)
