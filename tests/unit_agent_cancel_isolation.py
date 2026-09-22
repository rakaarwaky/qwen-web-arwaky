"""Regression tests for targeted cancellation across concurrent prompt runs."""

from __future__ import annotations

import inspect
import threading
from unittest.mock import MagicMock

from modules.core.src.agent_attachment_prompt_orchestrator import (
    AttachmentPromptOrchestrator,
)
from modules.core.src.agent_prompt_file_orchestrator import (
    PromptFileOrchestrator,
)
from modules.core.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.shared.src.taxonomy_core_vo import RunState


def _make_file_orchestrator(cancel: CapabilitiesRunCancelRegistry) -> PromptFileOrchestrator:
    return PromptFileOrchestrator(*(MagicMock() for _ in range(7)), cancel=cancel)


def _make_attachment_orchestrator(cancel: CapabilitiesRunCancelRegistry) -> AttachmentPromptOrchestrator:
    return AttachmentPromptOrchestrator(*(MagicMock() for _ in range(9)), cancel=cancel)


def test_file_orchestrator_cancel_only_closes_target_context() -> None:
    """Cancelling one file run does not set or close its sibling run."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator = _make_file_orchestrator(cancel)
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


def test_attachment_orchestrator_cancel_only_closes_target_context() -> None:
    """Cancelling one attachment run does not set or close its sibling run."""
    cancel = CapabilitiesRunCancelRegistry()
    orchestrator = _make_attachment_orchestrator(cancel)
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


class TestCancelContract:
    """Issue #360: request_cancel is a first-class contract operation."""

    def test_attachment_aggregate_contract_declares_request_cancel(self) -> None:
        from modules.shared.src.contract_core_aggregate import IAttachmentPromptAggregate

        assert callable(getattr(IAttachmentPromptAggregate, "request_cancel", None))

    def test_file_aggregate_contract_declares_request_cancel(self) -> None:
        from modules.shared.src.contract_core_aggregate import IPromptFileAggregate

        assert callable(getattr(IPromptFileAggregate, "request_cancel", None))

    def test_swarm_calls_request_cancel_without_getattr_hack(self) -> None:
        from modules.core.src.agent_swarm_orchestrator import SwarmOrchestrator

        src = inspect.getsource(SwarmOrchestrator._request_attachment_cancel)
        # direct typed contract call (no duck-typing escape hatch)
        assert "self._attachment.request_cancel(event)" in src
        assert "callable(" not in src
