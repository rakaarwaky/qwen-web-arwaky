"""Contract tests for shared module — verifies protocol/aggregate implementations exist."""

from __future__ import annotations

import pytest

from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleGate
from modules.shared.src.taxonomy_core_error import QwenCliError, ErrorCategory
from modules.shared.src.taxonomy_core_event import LifecycleEvent, STANDARD_PROMPT_EVENTS
from modules.shared.src.contract_core_protocol import IBrowserProtocol, ISendProtocol, IStreamProtocol
from modules.shared.src.contract_core_aggregate import (
    IDirectPromptAggregate,
    IAttachmentPromptAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
    ISetupAggregate,
    IPromptFlowAggregate,
    IJobManagerAggregate,
)


class TestSharedContracts:
    """Verify shared contract ABCs are implemented correctly."""

    def test_core_protocol_exists(self):
        assert hasattr(IBrowserProtocol, "__abstractmethods__")
        assert hasattr(ISendProtocol, "__abstractmethods__")
        assert hasattr(IStreamProtocol, "__abstractmethods__")

    def test_core_aggregate_exists(self):
        assert hasattr(IDirectPromptAggregate, "__abstractmethods__")
        assert hasattr(ISessionAggregate, "__abstractmethods__")

    def test_qwen_cli_error_is_exception(self):
        assert issubclass(QwenCliError, Exception)

    def test_error_category_enum(self):
        assert hasattr(ErrorCategory, "BROWSER_ERROR")
        assert hasattr(ErrorCategory, "NETWORK_ERROR")

    def test_lifecycle_emitter_emit(self):
        emitter = LifecycleEmitter()
        event = emitter.emit("test_event", detail="data")
        assert isinstance(event, LifecycleEvent)
        assert event.name == "test_event"

    def test_standard_prompt_events_defined(self):
        assert len(STANDARD_PROMPT_EVENTS) > 0

    def test_lifecycle_gate_states(self):
        gate = LifecycleGate()
        assert gate.state is not None
