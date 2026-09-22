"""Regression tests for the shared taxonomy event/error refactor."""

from dataclasses import FrozenInstanceError

import pytest

from modules.shared.src import (
    EVENT_FILE_UPLOADED,
    EVENT_ORDER,
    EVENT_PROMPT_INJECTED,
    EVENT_WEB_LOADED,
    PIPELINE_EVENT_SEQUENCE,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleGate, LifecycleState
from modules.shared.src.taxonomy_core_error import (
    ErrorCategory,
    QwenCliError,
    ResponseDetectionTimeoutError,
    StuckDetectedError,
)
from modules.shared.src.taxonomy_core_error import QwenCliError as CANONICAL_QWEN_CLI_ERROR
from modules.shared.src.taxonomy_core_event import (
    EVENT_DOCUMENT_PARSED,
    EVENT_GENERATION_FINISHED,
    EVENT_OUTPUT_COPIED,
    EVENT_SEND_CLICKED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    LifecycleEvent,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import (
    EVENT_WEB_LOADED as LEGACY_EVENT_WEB_LOADED,
)
from modules.shared.src.taxonomy_core_vo import (
    EventDetails,
    EventOrderMap,
)


def test_pipeline_event_sequence_is_canonical_and_ordered() -> None:
    assert PIPELINE_EVENT_SEQUENCE == (
        QwenEventType.WEB_LOADED,
        QwenEventType.LOGIN_VERIFIED,
        QwenEventType.MODEL_VERIFIED,
        QwenEventType.FILE_UPLOADED,
        QwenEventType.DOCUMENT_PARSED,
        QwenEventType.PROMPT_INJECTED,
        QwenEventType.SEND_CLICKED,
        QwenEventType.DISPATCH_ACKNOWLEDGED,
        QwenEventType.THINKING_STARTED,
        QwenEventType.STREAMING_GENERATION,
        QwenEventType.GENERATION_FINISHED,
        QwenEventType.OUTPUT_COPIED,
    )
    assert EVENT_ORDER[QwenEventType.WEB_LOADED] < EVENT_ORDER[QwenEventType.LOGIN_VERIFIED]
    assert EVENT_ORDER[QwenEventType.LOGIN_VERIFIED] < EVENT_ORDER[QwenEventType.MODEL_VERIFIED]
    assert EVENT_ORDER[QwenEventType.MODEL_VERIFIED] < EVENT_ORDER[QwenEventType.FILE_UPLOADED]
    assert EVENT_ORDER[QwenEventType.FILE_UPLOADED] < EVENT_ORDER[QwenEventType.DOCUMENT_PARSED]
    assert EVENT_ORDER[QwenEventType.DOCUMENT_PARSED] < EVENT_ORDER[QwenEventType.PROMPT_INJECTED]
    assert EVENT_ORDER[QwenEventType.DOCUMENT_PARSED] < EVENT_ORDER[QwenEventType.SEND_CLICKED]
    assert EVENT_ORDER[QwenEventType.SEND_CLICKED] < EVENT_ORDER[QwenEventType.DISPATCH_ACKNOWLEDGED]
    assert EVENT_ORDER[QwenEventType.DISPATCH_ACKNOWLEDGED] < EVENT_ORDER[QwenEventType.THINKING_STARTED]
    assert EVENT_ORDER[QwenEventType.THINKING_STARTED] < EVENT_ORDER[QwenEventType.STREAMING_GENERATION]
    assert EVENT_ORDER[QwenEventType.STREAMING_GENERATION] < EVENT_ORDER[QwenEventType.GENERATION_FINISHED]
    assert EVENT_ORDER[QwenEventType.GENERATION_FINISHED] < EVENT_ORDER[QwenEventType.OUTPUT_COPIED]


def test_event_exports_are_available_and_legacy_vo_alias_is_compatible() -> None:
    assert EVENT_WEB_LOADED == LEGACY_EVENT_WEB_LOADED
    assert EVENT_FILE_UPLOADED == QwenEventType.FILE_UPLOADED
    assert EVENT_PROMPT_INJECTED == QwenEventType.PROMPT_INJECTED
    assert EVENT_DOCUMENT_PARSED == QwenEventType.DOCUMENT_PARSED
    assert EVENT_SEND_CLICKED == QwenEventType.SEND_CLICKED
    assert EVENT_THINKING_STARTED == QwenEventType.THINKING_STARTED
    assert EVENT_STREAMING_GENERATION == QwenEventType.STREAMING_GENERATION
    assert EVENT_GENERATION_FINISHED == QwenEventType.GENERATION_FINISHED
    assert EVENT_OUTPUT_COPIED == QwenEventType.OUTPUT_COPIED


def test_lifecycle_event_is_immutable_and_legacy_vo_classes_are_constructible() -> None:
    details = EventDetails({"source": "test"})
    event = LifecycleEvent(name="EVENT_TEST", details=details)

    assert isinstance(details, EventDetails)
    assert isinstance(EventOrderMap({QwenEventType.WEB_LOADED: 0}), EventOrderMap)
    assert dict(event.details) == {"source": "test"}
    with pytest.raises(TypeError):
        event.details["source"] = "changed"
    with pytest.raises(FrozenInstanceError):
        event.name = "EVENT_CHANGED"


def test_entity_remains_for_stateful_runtime_behavior() -> None:
    state = LifecycleState()
    state.mark(EVENT_WEB_LOADED)
    assert state.web_loaded is True
    assert state.document_parsed is False
    assert isinstance(LifecycleEmitter(), LifecycleEmitter)


def test_lifecycle_gate_rejects_skipped_predecessors_and_records_reason() -> None:
    gate = LifecycleGate()
    gate.validate(QwenEventType.WEB_LOADED)
    with pytest.raises(RuntimeError, match="EVENT_DOCUMENT_PARSED"):
        gate.validate(QwenEventType.PROMPT_INJECTED)
    assert gate.rejections[0]["event"] == "EVENT_PROMPT_INJECTED"
    assert "EVENT_DOCUMENT_PARSED" in gate.rejections[0]["reason"]

    gate.validate(QwenEventType.LOGIN_VERIFIED)
    gate.validate(QwenEventType.MODEL_VERIFIED)
    gate.validate(QwenEventType.FILE_UPLOADED)
    with pytest.raises(RuntimeError, match="EVENT_DOCUMENT_PARSED"):
        gate.validate(QwenEventType.PROMPT_INJECTED)


def test_error_taxonomy_has_new_source_and_legacy_facade() -> None:
    assert CANONICAL_QWEN_CLI_ERROR is QwenCliError
    assert ErrorCategory.categorize(RuntimeError("network timeout")) == "network"
    assert (
        ErrorCategory.categorize(ResponseDetectionTimeoutError("Response detection timeout after 10s"))
        == "response_timeout"
    )
    assert ErrorCategory.categorize(StuckDetectedError("stuck: no forward event for 300s")) == "stuck"
