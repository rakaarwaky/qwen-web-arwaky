"""Regression tests for targeted cancellation across concurrent prompt runs."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from modules.core.src.agent_attachment_prompt_orchestrator import (
    AttachmentPromptOrchestrator,
)
from modules.core.src.agent_attachment_prompt_orchestrator import (
    _RunState as AttachmentRunState,
)
from modules.core.src.agent_prompt_file_orchestrator import (
    PromptFileOrchestrator,
)
from modules.core.src.agent_prompt_file_orchestrator import (
    _RunState as FileRunState,
)


def test_file_orchestrator_cancel_only_closes_target_context() -> None:
    """Cancelling one file run does not set or close its sibling run."""
    orchestrator = PromptFileOrchestrator(*(MagicMock() for _ in range(7)))
    first_event = threading.Event()
    second_event = threading.Event()
    first_context = MagicMock()
    second_context = MagicMock()
    orchestrator._run_registry = {
        first_event: FileRunState(cancel_event=first_event, active_bctx=first_context),
        second_event: FileRunState(cancel_event=second_event, active_bctx=second_context),
    }

    orchestrator.request_cancel(first_event)

    assert first_event.is_set()
    assert not second_event.is_set()
    first_context.close.assert_called_once_with()
    second_context.close.assert_not_called()


def test_attachment_orchestrator_cancel_only_closes_target_context() -> None:
    """Cancelling one attachment run does not set or close its sibling run."""
    orchestrator = AttachmentPromptOrchestrator(*(MagicMock() for _ in range(9)))
    first_event = threading.Event()
    second_event = threading.Event()
    first_context = MagicMock()
    second_context = MagicMock()
    orchestrator._run_registry = {
        first_event: AttachmentRunState(cancel_event=first_event, active_bctx=first_context),
        second_event: AttachmentRunState(cancel_event=second_event, active_bctx=second_context),
    }

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
        import inspect

        from modules.core.src.agent_swarm_orchestrator import SwarmOrchestrator

        src = inspect.getsource(SwarmOrchestrator._request_attachment_cancel)
        assert "getattr" not in src
        assert "self._attachment.request_cancel(event)" in src
