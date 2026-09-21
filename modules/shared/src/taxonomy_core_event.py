"""Taxonomy definitions for qwen-web lifecycle events.

This module contains only event values and immutable event payload contracts.
Stateful event emission and lifecycle state live in ``taxonomy_core_entity``.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import NewType, TypeAlias

from .taxonomy_core_vo import (
    EventDetails as EventDetailsValue,
)
from .taxonomy_core_vo import (
    EventDetailsMapping,
    EventId,
    EventName,
    EventOrderMapping,
    EventTimestamp,
)
from .taxonomy_core_vo import (
    EventOrderMap as EventOrderMapValue,
)

EventDetails: TypeAlias = EventDetailsMapping
EventOrderMap: TypeAlias = EventOrderMapping


class QwenEventType(str, Enum):
    """Ordered lifecycle events emitted by the qwen-web pipeline."""

    def __str__(self) -> str:
        """Return the wire name of the event."""
        return str(self.value)

    NETWORK_RECONNECTING = "EVENT_NETWORK_RECONNECTING"
    WEB_LOADED = "EVENT_WEB_LOADED"
    FILE_UPLOADED = "EVENT_FILE_UPLOADED"
    PROMPT_INJECTED = "EVENT_PROMPT_INJECTED"
    DOCUMENT_PARSED = "EVENT_DOCUMENT_PARSED"
    SEND_CLICKED = "EVENT_SEND_CLICKED"
    DISPATCH_ACKNOWLEDGED = "EVENT_DISPATCH_ACKNOWLEDGED"
    THINKING_STARTED = "EVENT_THINKING_STARTED"
    STREAMING_GENERATION = "EVENT_STREAMING_GENERATION"
    GENERATION_FINISHED = "EVENT_GENERATION_FINISHED"
    OUTPUT_COPIED = "EVENT_OUTPUT_COPIED"
    LOGIN_VERIFIED = "EVENT_LOGIN_VERIFIED"
    MODEL_VERIFIED = "EVENT_MODEL_VERIFIED"
    FAILED = "EVENT_FAILED"


EVENT_NETWORK_RECONNECTING = QwenEventType.NETWORK_RECONNECTING
EVENT_WEB_LOADED = QwenEventType.WEB_LOADED
EVENT_FILE_UPLOADED = QwenEventType.FILE_UPLOADED
EVENT_PROMPT_INJECTED = QwenEventType.PROMPT_INJECTED
EVENT_DOCUMENT_PARSED = QwenEventType.DOCUMENT_PARSED
EVENT_SEND_CLICKED = QwenEventType.SEND_CLICKED
EVENT_DISPATCH_ACKNOWLEDGED = QwenEventType.DISPATCH_ACKNOWLEDGED
EVENT_THINKING_STARTED = QwenEventType.THINKING_STARTED
EVENT_STREAMING_GENERATION = QwenEventType.STREAMING_GENERATION
EVENT_GENERATION_FINISHED = QwenEventType.GENERATION_FINISHED
EVENT_OUTPUT_COPIED = QwenEventType.OUTPUT_COPIED
EVENT_LOGIN_VERIFIED = QwenEventType.LOGIN_VERIFIED
EVENT_MODEL_VERIFIED = QwenEventType.MODEL_VERIFIED
EVENT_FAILED = QwenEventType.FAILED


PIPELINE_EVENT_SEQUENCE: tuple[QwenEventType, ...] = (
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

STANDARD_PROMPT_EVENTS: tuple[QwenEventType, ...] = (
    QwenEventType.WEB_LOADED,
    QwenEventType.LOGIN_VERIFIED,
    QwenEventType.MODEL_VERIFIED,
    QwenEventType.PROMPT_INJECTED,
    QwenEventType.SEND_CLICKED,
    QwenEventType.DISPATCH_ACKNOWLEDGED,
    QwenEventType.THINKING_STARTED,
    QwenEventType.STREAMING_GENERATION,
    QwenEventType.GENERATION_FINISHED,
    QwenEventType.OUTPUT_COPIED,
)

EVENT_ORDER: EventOrderMapValue = EventOrderMapValue(
    {event: index for index, event in enumerate(PIPELINE_EVENT_SEQUENCE)}
)


@dataclass(frozen=True)
class LifecycleEvent:
    """Structured event emitted at a lifecycle boundary."""

    name: EventName
    timestamp: EventTimestamp = field(default_factory=time.time)
    event_id: EventId = field(default_factory=lambda: uuid.uuid4().hex)
    details: EventDetails = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze detail payloads so callbacks observe the same event state."""
        immutable_details = MappingProxyType(EventDetailsValue(self.details))
        object.__setattr__(self, "details", immutable_details)


LifecycleCallback = Callable[[LifecycleEvent], None]
EventMessage = NewType("EventMessage", str)
CallbackRegistry = dict[str, list[LifecycleCallback]]


EVENT_DESCRIPTIONS: dict[QwenEventType, str] = {
    QwenEventType.NETWORK_RECONNECTING: "Reconnecting to Qwen Web...",
    QwenEventType.WEB_LOADED: "Qwen Web page loaded",
    QwenEventType.FILE_UPLOADED: "Prompt file uploaded",
    QwenEventType.PROMPT_INJECTED: "Prompt injected into the composer",
    QwenEventType.DOCUMENT_PARSED: "Prompt/document parsed",
    QwenEventType.SEND_CLICKED: "Send button clicked",
    QwenEventType.DISPATCH_ACKNOWLEDGED: "Dispatch acknowledged",
    QwenEventType.THINKING_STARTED: "Qwen AI thinking...",
    QwenEventType.STREAMING_GENERATION: "Qwen AI typing...",
    QwenEventType.GENERATION_FINISHED: "Generation finished",
    QwenEventType.OUTPUT_COPIED: "Output saved",
    QwenEventType.LOGIN_VERIFIED: "Login session verified",
    QwenEventType.MODEL_VERIFIED: "Default model verified",
}

__all__ = [
    "QwenEventType",
    "LifecycleEvent",
    "LifecycleCallback",
    "EventDetails",
    "EventMessage",
    "CallbackRegistry",
    "EVENT_DESCRIPTIONS",
    "PIPELINE_EVENT_SEQUENCE",
    "STANDARD_PROMPT_EVENTS",
    "EVENT_ORDER",
    "EVENT_NETWORK_RECONNECTING",
    "EVENT_WEB_LOADED",
    "EVENT_FILE_UPLOADED",
    "EVENT_PROMPT_INJECTED",
    "EVENT_DOCUMENT_PARSED",
    "EVENT_SEND_CLICKED",
    "EVENT_DISPATCH_ACKNOWLEDGED",
    "EVENT_THINKING_STARTED",
    "EVENT_STREAMING_GENERATION",
    "EVENT_GENERATION_FINISHED",
    "EVENT_OUTPUT_COPIED",
    "EVENT_LOGIN_VERIFIED",
    "EVENT_MODEL_VERIFIED",
    "EVENT_FAILED",
]
