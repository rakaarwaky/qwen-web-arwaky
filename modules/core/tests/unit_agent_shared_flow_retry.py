"""Regression test: dispatch retry must not be killed by the lifecycle gate.

Reproduces the swarm failure where 10/10 agents died on attempt 2 with
"Lifecycle gate rejected EVENT_PROMPT_INJECTED: EVENT_PROMPT_INJECTED was
already emitted": the first attempt times out mid-wait, the retry re-emits
PROMPT_INJECTED, and a full gate reset had already discarded the page-phase
predecessors (WEB_LOADED/LOGIN_VERIFIED/MODEL_VERIFIED) that are never
re-emitted on retry.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.prompt.src.agent_shared_flow_orchestrator import SharedFlowOrchestrator
from modules.shared.src.taxonomy_core_constant import MAX_ATTEMPTS
from modules.shared.src.taxonomy_core_error import ResponseDetectionTimeoutError
from modules.shared.src.taxonomy_core_event import PIPELINE_EVENT_SEQUENCE, STANDARD_PROMPT_EVENTS
from modules.shared.src.taxonomy_core_vo import AppConfig, MessageCount
from modules.shared.src.utility_dom_helper import setup_lifecycle_state


def _make_cfg() -> AppConfig:
    return AppConfig(
        input_path=Path("/tmp/prompt.txt"),
        output_path=Path("/tmp/output.txt"),
        session_path=Path("/tmp/session"),
    )


def _make_sender(events, emitter) -> MagicMock:
    """A sender mock that emits SEND_CLICKED/DISPATCH_ACKNOWLEDGED on the
    real emitter so ``state.dispatch_acknowledged`` becomes True."""
    send_idx = events.index("EVENT_SEND_CLICKED")
    ack_idx = events.index("EVENT_DISPATCH_ACKNOWLEDGED")

    def click_send_stub(_page, _emitter, **_kwargs):
        _emitter.emit(events[send_idx])
        _emitter.emit(events[ack_idx])

    sender = MagicMock()
    sender.click_send.side_effect = click_send_stub
    return sender


def _run_once(
    flow: SharedFlowOrchestrator,
    emitter,
    state,
    streamer: MagicMock,
    observability: MagicMock,
    events=STANDARD_PROMPT_EVENTS,
) -> str:
    sender = _make_sender(events, emitter)
    return flow.dispatch_and_wait_for_response(
        page=MagicMock(),
        injector=MagicMock(),
        sender=sender,
        streamer=streamer,
        emitter=emitter,
        state=state,
        observability=observability,
        filepath=Path("/tmp/prompt.txt"),
        prompt="hello",
        msg_count_before=MessageCount(0),
        timeout_sec=60,
        active_cfg=_make_cfg(),
    )


def test_dispatch_retry_survives_first_attempt_timeout() -> None:
    """Standard pipeline: attempt 1 times out mid-wait; attempt 2 must pass
    the gate after the prefix-preserving reset and complete the run."""
    flow = SharedFlowOrchestrator()
    observability = MagicMock()
    logger = MagicMock()

    emitter, state = setup_lifecycle_state(logger, STANDARD_PROMPT_EVENTS)
    for event in STANDARD_PROMPT_EVENTS[:3]:
        emitter.emit(event)

    streamer = MagicMock()
    streamer.wait_for_response.side_effect = [
        ResponseDetectionTimeoutError("no terminal response event detected"),
        "final response",
    ]

    with patch("modules.prompt.src.agent_shared_flow_orchestrator.time.sleep"):
        response = _run_once(flow, emitter, state, streamer, observability)

    assert response == "final response"
    assert streamer.wait_for_response.call_count == 2
    assert state.dispatch_acknowledged is True


def test_dispatch_retry_reraises_on_max_attempts() -> None:
    flow = SharedFlowOrchestrator()
    observability = MagicMock()
    logger = MagicMock()

    emitter, state = setup_lifecycle_state(logger, STANDARD_PROMPT_EVENTS)
    for event in STANDARD_PROMPT_EVENTS[:3]:
        emitter.emit(event)

    streamer = MagicMock()
    streamer.wait_for_response.side_effect = ResponseDetectionTimeoutError("always times out")

    with patch("modules.prompt.src.agent_shared_flow_orchestrator.time.sleep"):
        with pytest.raises(ResponseDetectionTimeoutError):
            _run_once(flow, emitter, state, streamer, observability)

    assert streamer.wait_for_response.call_count == MAX_ATTEMPTS


def test_reset_rolls_back_a_started_attempt_full_sequence() -> None:
    """A stall past PROMPT_INJECTED/SEND_CLICKED (events already accepted)
    must be rolled back to the pre-attempt prefix (boundary = index of
    PROMPT_INJECTED in STANDARD_PROMPT_EVENTS = 3) on reset, then the full
    per-attempt sequence re-validated in one pass."""
    emitter, _state = setup_lifecycle_state(MagicMock(), STANDARD_PROMPT_EVENTS)
    gate = emitter.gate
    assert gate is not None

    for event in STANDARD_PROMPT_EVENTS[:7]:
        gate.validate(event)

    # Boundary for the standard pipeline: index of PROMPT_INJECTED = 3
    # (WEB_LOADED, LOGIN_VERIFIED, MODEL_VERIFIED kept; PROMPT_INJECTED
    # and onward rolled back).
    gate.reset(completed_prefix=gate.completed[:3])
    assert gate.completed == tuple(STANDARD_PROMPT_EVENTS[:3])

    for event in STANDARD_PROMPT_EVENTS[3:]:
        gate.validate(event)
    assert gate.completed == tuple(STANDARD_PROMPT_EVENTS)


def test_attachment_pipeline_retry_preserves_document_parsed() -> None:
    """Attachment pipeline: DOCUMENT_PARSED is emitted once before the dispatch loop.
    After a timeout retry, the gate must still accept PROMPT_INJECTED because
    DOCUMENT_PARSED remains in the completed prefix (boundary = index+1 = 5)."""
    flow = SharedFlowOrchestrator()
    observability = MagicMock()
    logger = MagicMock()

    emitter, state = setup_lifecycle_state(logger, PIPELINE_EVENT_SEQUENCE)
    # Simulate pre-attempt events (page load, login, model, file upload, document parsed)
    for event in PIPELINE_EVENT_SEQUENCE[:5]:  # WEB_LOADED through DOCUMENT_PARSED
        emitter.emit(event)

    streamer = MagicMock()
    streamer.wait_for_response.side_effect = [
        ResponseDetectionTimeoutError("no terminal response event detected"),
        "final response",
    ]

    with patch("modules.prompt.src.agent_shared_flow_orchestrator.time.sleep"):
        response = _run_once(flow, emitter, state, streamer, observability, PIPELINE_EVENT_SEQUENCE)

    assert response == "final response"
    assert streamer.wait_for_response.call_count == 2
    assert state.dispatch_acknowledged is True
    # Verify DOCUMENT_PARSED is preserved in gate after reset
    gate = emitter.gate
    assert gate is not None
    assert "EVENT_DOCUMENT_PARSED" in [str(e) for e in gate.completed]
