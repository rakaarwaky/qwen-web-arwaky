"""Regression tests for targeted cancellation across concurrent prompt runs."""

from __future__ import annotations

import inspect
import threading
from unittest.mock import MagicMock

import pytest

from modules.prompt.src.capabilities_attachment_prompt_adapter import (
    AttachmentPromptAdapter,
)
from modules.prompt.src.capabilities_prompt_file_adapter import (
    PromptFileAdapter,
)
from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.shared.src.taxonomy_core_vo import RunState


def _make_file_orchestrator(cancel: CapabilitiesRunCancelRegistry) -> PromptFileAdapter:
    return PromptFileAdapter(*(MagicMock() for _ in range(7)), cancel=cancel)


def _make_attachment_orchestrator(cancel: CapabilitiesRunCancelRegistry) -> AttachmentPromptAdapter:
    return AttachmentPromptAdapter(*(MagicMock() for _ in range(9)), cancel=cancel)


@pytest.mark.parametrize(
    "orchestrator_factory",
    [_make_file_orchestrator, _make_attachment_orchestrator],
    ids=["file", "attachment"],
)
def test_orchestrator_cancel_only_closes_target_context(orchestrator_factory) -> None:
    """Cancelling one run does not set or close its sibling run, for the
    file and attachment adapters alike."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator = orchestrator_factory(cancel)
    first_event = threading.Event()
    second_event = threading.Event()
    first_context = MagicMock()
    second_context = MagicMock()
    cancel.register(RunState(cancel_event=first_event, active_bctx=first_context))
    cancel.register(RunState(cancel_event=second_event, active_bctx=second_context))

    orchestrator.request_cancel(first_event)

    assert first_event.is_set()
    assert not second_event.is_set()
    first_context.close.assert_called_once_with()
    second_context.close.assert_not_called()


def test_registry_is_keyed_by_run_id_not_object_identity() -> None:
    """Issue #361: the registry addresses runs by a stable RunId, not id(event)."""
    cancel = CapabilitiesRunCancelRegistry()
    event = threading.Event()
    state = RunState(cancel_event=event)
    cancel.register(state)

    assert cancel.active_bctx(state.run_id) is None
    cancel.cancel_run(state.run_id)
    assert event.is_set()

    # The same stable id cancels the run even when the caller no longer holds
    # the event object it originally passed in.
    cancel.release(state)
    assert event.is_set()


def test_release_drops_the_event_index_entry() -> None:
    """Issue #361: a released run can no longer be cancelled by its old event."""
    cancel = CapabilitiesRunCancelRegistry()
    event = threading.Event()
    state = RunState(cancel_event=event)
    cancel.register(state)
    cancel.release(state)

    cancel.cancel_by_event(event)

    assert not event.is_set()


class TestCancelContract:
    """Issue #360: request_cancel is a first-class contract operation."""

    def test_swarm_calls_request_cancel_without_getattr_hack(self) -> None:

        from modules.swarm.src.capabilities_swarm_runner import SwarmRunner

        src = inspect.getsource(SwarmRunner._request_attachment_cancel)
        # direct typed contract call (no duck-typing escape hatch)
        assert "self._attachment.execute(" in src
        assert 'PromptRequest(verb="request_cancel"' in src
        assert "callable(" not in src
