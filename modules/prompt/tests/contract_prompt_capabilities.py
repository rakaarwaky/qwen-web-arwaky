"""Contract tests for the prompt capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.prompt.src.capabilities_prompt_injector import PromptInjector
from modules.prompt.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.contract_core_protocol import (
    IInjectionProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.contract_prompt_protocol import (
    IAttachmentPromptProtocol,
    IDirectPromptProtocol,
    IPromptFileProtocol,
    IPromptFlowProtocol,
)

_REQUIRED_PROTOCOLS: tuple[type, ...] = (
    IInjectionProtocol,
    ISendProtocol,
    IStreamProtocol,
    IDirectPromptProtocol,
    IAttachmentPromptProtocol,
    IPromptFileProtocol,
)


def test_injector_implements_the_injection_protocol() -> None:
    assert IInjectionProtocol in inspect.getmro(PromptInjector)


def test_sender_implements_the_send_protocol() -> None:
    assert ISendProtocol in inspect.getmro(SendDispatcher)


def test_streamer_implements_the_stream_protocol() -> None:
    assert IStreamProtocol in inspect.getmro(StreamMonitor)


def test_the_flow_capability_declares_only_the_one_door() -> None:
    public = {name for name, _ in inspect.getmembers(IPromptFlowProtocol, predicate=inspect.isfunction)}
    assert public == {"dispatch_and_wait_for_response"}


def test_every_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for protocol in _REQUIRED_PROTOCOLS:
        for name, _ in inspect.getmembers(protocol, predicate=inspect.isfunction):
            signature = inspect.signature(getattr(protocol, name))
            assert signature.return_annotation is not inspect.Signature.empty, (
                f"{protocol.__name__}.{name} has no return"
            )
