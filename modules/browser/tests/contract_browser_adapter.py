"""Contract tests for the browser capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.browser.src.capabilities_browser_adapter import BrowserAdapter
from modules.shared.src.contract_browser_aggregate import IBrowserAggregate
from modules.shared.src.contract_core_protocol import IBrowserProtocol

_REQUIRED_PROTOCOL_METHODS: frozenset[str] = frozenset(
    {"browser_session", "check_auth", "check_session", "navigate_to_chat", "reset_page"}
)


def test_adapter_implements_the_browser_protocol() -> None:
    assert isinstance(BrowserAdapter(), IBrowserProtocol)


def test_aggregate_declares_only_the_open_session_door() -> None:
    public = {name for name, _ in inspect.getmembers(IBrowserAggregate, predicate=inspect.isfunction)}
    assert public == {"open_session"}


def test_protocol_declares_exactly_the_sealed_method_set() -> None:
    public = {name for name, _ in inspect.getmembers(IBrowserProtocol, predicate=inspect.isfunction)}
    assert public == set(_REQUIRED_PROTOCOL_METHODS)


def test_every_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for name in _REQUIRED_PROTOCOL_METHODS:
        signature = inspect.signature(getattr(IBrowserProtocol, name))
        assert signature.return_annotation is not inspect.Signature.empty, f"{name} has no return annotation"
