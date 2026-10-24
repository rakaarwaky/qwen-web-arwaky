"""Pinned-navigation regression for the browser adapter's DOM selectors.

BROWSER-02 (FR-BROWSER-002): the browser suite pins the navigation retry
paths (textarea hydration wait, new-chat reset, model-picker retry, expiry
banner probe) against a captured chat.qwen.ai DOM snapshot. A renamed class
or a selector the adapter no longer matches fails this test before it
fails a live run.

Two guards:

1. **Selector drift guard** — every pinned selector constant the
   navigation retry paths use must still match a node in the pinned
   fixture. If the live DOM renames a class or the constants drift, the
   match fails here.

2. **Drift detection** — renaming a class in the fixture must make the
   guard fail, proving the test actually pins the vocabulary.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from modules.shared.src.common.taxonomy_core_constant import (
    MODEL_SELECTOR_BUTTON,
    NEW_CHAT_SELECTORS,
    SESSION_EXPIRED_BANNER_SELECTORS,
    SESSION_EXPIRED_KEYWORDS,
    TEXTAREA_SELECTOR,
)

FIXTURE = Path(__file__).parent / "fixtures" / "navigation_dom_chat.html"

SCENARIOS: tuple[str, ...] = ("chat_ready", "chat_not_hydrated", "expired_banner")


def _load_fixture() -> str:
    assert FIXTURE.is_file(), f"the pinned navigation DOM fixture must exist at {FIXTURE}"
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
        self.visible = "hidden" not in attributes


class _NavigationDomParser(HTMLParser):
    """Parse one ``<section data-scenario>`` of the fixture into a node tree."""

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


def _walk(node: _Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _section_dom(html: str, scenario: str) -> _Node:
    """Return the root node of the fixture's ``data-scenario`` section."""
    parser = _NavigationDomParser()
    parser.feed(html)
    parser.close()
    for section in _walk(parser.root):
        if section.tag == "section" and section.attributes.get("data-scenario") == scenario:
            return section
    raise AssertionError(f'the fixture has no <section data-scenario="{scenario}">')


def _deep_text(node: _Node) -> str:
    return "".join(node.text for node in _walk(node) if node.tag not in ("script", "style"))


def _matches_simple(node: _Node, step: str) -> bool:
    """Evaluate one CSS step against a node (tag, class, aria-label, attributes).

    Supports the shapes that appear in the pinned constants:
    - ``[aria-label='New Chat']`` / ``[aria-label*='New chat' i]``
    - ``[class*='session-expired']``
    - ``.wms-list__item``
    - ``textarea.message-input-textarea`` (tag + class)
    - ``button[aria-label*='New chat' i]`` / ``div[aria-label*='New chat' i]``
    - ``input[type='password']``
    """
    step = step.strip()
    if not step:
        return True

    # tag+class compound: "textarea.message-input-textarea"
    if "." in step and not step.startswith(".") and "[" not in step:
        tag, _, class_token = step.partition(".")
        if node.tag != tag:
            return False
        return class_token in node.classes

    # tag[attribute] compound: "button[aria-label*='New chat' i]"
    m = re.match(r"^([a-z]+)\[(.*)\]$", step)
    if m:
        tag, attr_part = m.group(1), m.group(2)
        if node.tag != tag:
            return False
        return _matches_attr(node, attr_part)

    # bare class: ".wms-list__item"
    if step.startswith("."):
        class_token = re.split(r"[:.\[\]]", step[1:], maxsplit=1)[0]
        return class_token in node.classes

    # bare attribute: "[class*='session-expired']"
    if step.startswith("["):
        inner = step[1:]
        if inner.endswith("]"):
            inner = inner[:-1]
        return _matches_attr(node, inner)

    # bare tag
    return node.tag == step


def _matches_attr(node: _Node, attr_part: str) -> bool:
    """Evaluate a bracket attribute expression against a node.

    ``attr_part`` is the content inside the brackets, e.g.
    ``aria-label*='New chat' i`` or ``class*='session-expired'``.
    """
    # Strip trailing case-insensitivity flag
    attr_part = re.sub(r"\s+i$", "", attr_part)

    if "*=" in attr_part:
        # substring match on attribute (e.g. class*='session-expired')
        m = re.match(r"^([\w-]+)\*=\s*(.*)$", attr_part)
        if m:
            key, raw_value = m.group(1), m.group(2)
            value = _unquote(raw_value)
            if key == "class":
                return any(value in cls for cls in node.classes)
            return value.lower() in node.attributes.get(key, "").lower()
    if "=" in attr_part:
        # exact match (e.g. aria-label='New Chat')
        m = re.match(r"^([\w-]+)=\s*(.*)$", attr_part)
        if m:
            key, raw_value = m.group(1), m.group(2)
            return node.attributes.get(key, "") == _unquote(raw_value)
    # bare attribute presence
    m = re.match(r"^([\w-]+)$", attr_part)
    if m:
        return m.group(1) in node.attributes
    return False


def _unquote(value: str) -> str:
    value = value.strip()
    if value[:1] in ("'", '"'):
        value = value[1:]
        if value and value[-1] in ("'", '"'):
            value = value[:-1]
    return value


def _select(root: _Node, selector: str) -> list[_Node]:
    """Evaluate the CSS vocabulary the pinned selectors use against the tree.

    The selector is a comma-separated union; each part is a single compound
    step (no descendant combinators are used in the pinned constants).
    """
    parts = [part.strip() for part in selector.split(",")]
    matches: list[_Node] = []
    for part in parts:
        if not part:
            continue
        matches.extend(_select_one(root, part))
    return matches


def _select_one(root: _Node, part: str) -> list[_Node]:
    """Descendant walk: every node under root matching the single-part selector."""
    found: list[_Node] = []
    for descendant in _walk(root):
        if _matches_simple(descendant, part):
            found.append(descendant)
    return found


# ─── Pinned selector constants extracted from the fixture ────────────────
# Each entry is (name, selector, expected_scenarios) — the selector must
# match a node in each of the listed scenarios. This is the pinning: if the
# production constant drifts from what the live DOM exposes, the match fails.


def _pin_entry(selector: str, present_in: tuple[str, ...], absent_in: tuple[str, ...] = ()) -> dict:
    return {"selector": selector, "present_in": present_in, "absent_in": absent_in}


def _pin_navigation_selectors() -> list[dict]:
    """Return the pinned selector table.

    Each entry names the production selector constant and the scenarios in
    which it must (present_in) / must not (absent_in) match a fixture node.
    """
    entries: list[dict] = []

    # Step 1 of navigate_to_chat: wait_for_selector(TEXTAREA_SELECTOR)
    entries.append(
        _pin_entry(
            TEXTAREA_SELECTOR,
            present_in=("chat_ready", "expired_banner"),
            absent_in=("chat_not_hydrated",),
        )
    )

    # _start_new_chat: click_first_visible_enabled(NEW_CHAT_SELECTORS)
    # The union is pinned: if every variant drifts the reset fails.
    new_chat_combined = ", ".join(NEW_CHAT_SELECTORS)
    entries.append(_pin_entry(new_chat_combined, present_in=("chat_ready",), absent_in=("chat_not_hydrated",)))

    # Model picker trigger: _get_model_trigger falls back to
    # page.get_by_role("button", name=MODEL_SELECTOR_BUTTON)
    model_trigger_selector = f"button[aria-label='{MODEL_SELECTOR_BUTTON}']"
    entries.append(_pin_entry(model_trigger_selector, present_in=("chat_ready",), absent_in=("chat_not_hydrated",)))

    # Model picker options: _select_first_available_model / _try_set_as_default
    # match `.wms-list__item`
    entries.append(_pin_entry(".wms-list__item", present_in=("chat_ready",), absent_in=("chat_not_hydrated",)))

    # Expiry banner: assert_on_chat_page / _in_page_expiry_banner_visible
    # check SESSION_EXPIRED_BANNER_SELECTORS against the body
    banner_combined = ", ".join(SESSION_EXPIRED_BANNER_SELECTORS)
    entries.append(
        _pin_entry(banner_combined, present_in=("expired_banner",), absent_in=("chat_ready", "chat_not_hydrated"))
    )

    return entries


def test_every_pinned_selector_matches_its_scenarios() -> None:
    html = _load_fixture()
    for entry in _pin_navigation_selectors():
        selector = entry["selector"]
        for scenario in entry["present_in"]:
            dom = _section_dom(html, scenario)
            matched = _select(dom, selector)
            assert matched, f"present_in={scenario}: selector '{selector}' no longer matches the fixture"
        for scenario in entry["absent_in"]:
            dom = _section_dom(html, scenario)
            matched = _select(dom, selector)
            assert not matched, f"absent_in={scenario}: selector '{selector}' unexpectedly matches the fixture"


def test_every_scenario_is_present_exactly_once() -> None:
    html = _load_fixture()
    parser = _NavigationDomParser()
    parser.feed(html)
    parser.close()
    sections = [n for n in _walk(parser.root) if n.tag == "section"]
    assert sorted(n.attributes.get("data-scenario", "") for n in sections) == sorted(SCENARIOS)


def test_a_renamed_class_in_the_fixture_fails_the_suite() -> None:
    """Selector drift: rename the textarea class and the guard must fire."""
    html = _load_fixture().replace("message-input-textarea", "message-input-box")
    dom = _section_dom(html, "chat_ready")
    matched = _select(dom, TEXTAREA_SELECTOR)
    assert not matched, "a renamed textarea class must break the pinned selector match"


def test_renamed_model_trigger_fails_the_suite() -> None:
    """The model picker trigger aria-label is pinned; a rename must fire."""
    html = _load_fixture().replace("Select Model", "Choose Model")
    dom = _section_dom(html, "chat_ready")
    trigger_selector = f"button[aria-label='{MODEL_SELECTOR_BUTTON}']"
    matched = _select(dom, trigger_selector)
    assert not matched, "a renamed model trigger label must break the pinned selector match"


def test_expiry_banner_selector_still_matches_the_banner_shell() -> None:
    """The expiry banner shells are pinned to the live DOM; a rename fires."""
    html = _load_fixture()
    dom = _section_dom(html, "expired_banner")
    banner_combined = ", ".join(SESSION_EXPIRED_BANNER_SELECTORS)
    matched = _select(dom, banner_combined)
    assert matched, "the expiry banner shells must still match the fixture banner"


def test_session_expired_keywords_are_pinned() -> None:
    """The keyword list is part of the navigation retry contract; drift fires."""
    body_text = _section_dom(_load_fixture(), "expired_banner")
    lowered = _deep_text(body_text).lower()
    assert any(kw in lowered for kw in SESSION_EXPIRED_KEYWORDS), (
        "the fixture banner body must carry at least one SESSION_EXPIRED_KEYWORDS entry"
    )


def test_chat_not_hydrated_lacks_the_textarea() -> None:
    """A DOM that is mid-hydration must not expose the input selector."""
    html = _load_fixture()
    dom = _section_dom(html, "chat_not_hydrated")
    assert not _select(dom, TEXTAREA_SELECTOR)


def test_chat_ready_exposes_the_textarea_and_new_chat() -> None:
    """A hydrated chat page must expose both the input and the reset button."""
    html = _load_fixture()
    dom = _section_dom(html, "chat_ready")
    assert _select(dom, TEXTAREA_SELECTOR), "chat_ready must expose the input textarea"
    new_chat_combined = ", ".join(NEW_CHAT_SELECTORS)
    assert _select(dom, new_chat_combined), "chat_ready must expose a New-Chat reset button"
