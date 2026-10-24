"""PROMPT-01 / CONFIG-02: the dispatch retry budget gates stall retries.

The wall-clock response ceiling (``timeout_sec``) is absolute and terminal
per attempt. The event-driven stall detector (``stall_timeout_sec``) is the
retriable boundary, and it spends one slot of the CONFIG-02 dispatch retry
budget (``AppConfig.dispatch_retry_budget``) per re-send. Budget 0 — the
default, pinned by ``unit_agent_shared_flow_retry.py`` and
``unit_transcript_selector_regression.py`` — keeps a stall terminal for the
run; a positive budget caps how many times the send may be retried.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
from modules.prompt.tests.unit_agent_shared_flow_retry import _make_cfg, _make_sender, _run_once
from modules.shared.src.common.taxonomy_core_constant import (
    DISPATCH_RETRY_BUDGET_ENV,
    MAX_ATTEMPTS,
)
from modules.shared.src.common.taxonomy_core_error import StuckDetectedError
from modules.shared.src.common.taxonomy_core_event import STANDARD_PROMPT_EVENTS
from modules.shared.src.common.taxonomy_core_vo import (
    AppConfig,
    MessageCount,
    TimeoutSec,
)
from modules.shared.src.common.utility_core_retry_budget import resolve_dispatch_retry_budget
from modules.shared.src.common.utility_dom_helper import setup_lifecycle_state


def _stalling_streamer() -> MagicMock:
    """A streamer whose wait always raises the stall detector's error."""

    def wait_for_response_stub(*_args, **_kwargs):
        raise StuckDetectedError("no forward lifecycle event for 300s")

    streamer = MagicMock()
    streamer.wait_for_response.side_effect = wait_for_response_stub
    return streamer


def test_budget_zero_keeps_a_stall_terminal() -> None:
    """Default budget: one stall, one attempt, the error is terminal (FRD pin)."""
    flow = PromptFlowDispatcher()
    observability = MagicMock()
    logger = MagicMock()

    emitter, state = setup_lifecycle_state(logger, STANDARD_PROMPT_EVENTS)
    for event in STANDARD_PROMPT_EVENTS[:3]:
        emitter.emit(event)

    streamer = _stalling_streamer()
    with patch("modules.prompt.src.capabilities_prompt_flow_dispatcher.time.sleep"):
        with pytest.raises(StuckDetectedError, match="no forward lifecycle event"):
            _run_once(flow, emitter, state, streamer, observability)

    assert streamer.wait_for_response.call_count == 1


def test_budget_two_allows_two_stall_retries() -> None:
    """A CONFIG-02 budget of 2 spends two extra attempts before the stall is terminal."""
    flow = PromptFlowDispatcher()
    observability = MagicMock()
    logger = MagicMock()

    emitter, state = setup_lifecycle_state(logger, STANDARD_PROMPT_EVENTS)
    for event in STANDARD_PROMPT_EVENTS[:3]:
        emitter.emit(event)

    cfg = _make_cfg()
    cfg = AppConfig(
        input_path=cfg.input_path,
        output_path=cfg.output_path,
        session_path=cfg.session_path,
        dispatch_retry_budget=2,
    )

    streamer = MagicMock()
    streamer.wait_for_response.side_effect = lambda *_a, **_kw: (_ for _ in ()).throw(
        StuckDetectedError("no forward lifecycle event for 300s")
    )

    with patch("modules.prompt.src.capabilities_prompt_flow_dispatcher.time.sleep"):
        with pytest.raises(StuckDetectedError, match="no forward lifecycle event"):
            flow.dispatch_and_wait_for_response(
                page=MagicMock(),
                filepath=Path("/tmp/prompt.txt"),
                prompt="hello",
                msg_count_before=MessageCount(0),
                timeout_sec=TimeoutSec(60),
                active_cfg=cfg,
                emitter=emitter,
                state=state,
                observability=observability,
                injector=MagicMock(),
                sender=_make_sender(STANDARD_PROMPT_EVENTS),
                streamer=streamer,
            )

    # One initial attempt plus the two budgeted retries.
    assert streamer.wait_for_response.call_count == 3
    assert streamer.wait_for_response.call_count <= MAX_ATTEMPTS


def test_budget_exhausts_max_attempts_cap() -> None:
    """A budget above MAX_ATTEMPTS still cannot exceed the loop ceiling."""
    flow = PromptFlowDispatcher()
    observability = MagicMock()
    logger = MagicMock()

    emitter, state = setup_lifecycle_state(logger, STANDARD_PROMPT_EVENTS)
    for event in STANDARD_PROMPT_EVENTS[:3]:
        emitter.emit(event)

    cfg = _make_cfg()
    cfg = AppConfig(
        input_path=cfg.input_path,
        output_path=cfg.output_path,
        session_path=cfg.session_path,
        dispatch_retry_budget=10,
    )

    streamer = MagicMock()
    streamer.wait_for_response.side_effect = lambda *_a, **_kw: (_ for _ in ()).throw(
        StuckDetectedError("no forward lifecycle event for 300s")
    )

    with patch("modules.prompt.src.capabilities_prompt_flow_dispatcher.time.sleep"):
        with pytest.raises(StuckDetectedError, match="no forward lifecycle event"):
            flow.dispatch_and_wait_for_response(
                page=MagicMock(),
                filepath=Path("/tmp/prompt.txt"),
                prompt="hello",
                msg_count_before=MessageCount(0),
                timeout_sec=TimeoutSec(60),
                active_cfg=cfg,
                emitter=emitter,
                state=state,
                observability=observability,
                injector=MagicMock(),
                sender=_make_sender(STANDARD_PROMPT_EVENTS),
                streamer=streamer,
            )

    assert streamer.wait_for_response.call_count == MAX_ATTEMPTS


def test_stall_retries_rolled_back_from_the_attempt_boundary() -> None:
    """A retried stall re-emits the full per-attempt sequence after the prefix-preserving reset."""
    flow = PromptFlowDispatcher()
    observability = MagicMock()
    logger = MagicMock()

    emitter, state = setup_lifecycle_state(logger, STANDARD_PROMPT_EVENTS)
    for event in STANDARD_PROMPT_EVENTS[:3]:
        emitter.emit(event)

    cfg = _make_cfg()
    cfg = AppConfig(
        input_path=cfg.input_path,
        output_path=cfg.output_path,
        session_path=cfg.session_path,
        dispatch_retry_budget=1,
    )

    waits = [
        StuckDetectedError("no forward lifecycle event for 300s"),
        MagicMock(text="recovered response", verdict="complete"),
    ]

    def wait_for_response_stub(*_args, **_kwargs):
        result = waits.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    streamer = MagicMock()
    streamer.wait_for_response.side_effect = wait_for_response_stub

    with patch("modules.prompt.src.capabilities_prompt_flow_dispatcher.time.sleep"):
        verdict = flow.dispatch_and_wait_for_response(
            page=MagicMock(),
            filepath=Path("/tmp/prompt.txt"),
            prompt="hello",
            msg_count_before=MessageCount(0),
            timeout_sec=TimeoutSec(60),
            active_cfg=cfg,
            emitter=emitter,
            state=state,
            observability=observability,
            injector=MagicMock(),
            sender=_make_sender(STANDARD_PROMPT_EVENTS),
            streamer=streamer,
        )

    assert str(verdict.text) == "recovered response"
    assert streamer.wait_for_response.call_count == 2
    # The gate survived the stall reset with the pre-attempt prefix; the
    # recovered attempt re-walked from that boundary, so the terminal
    # events past it (thinking, streaming, finished) are not all present.
    gate = emitter.gate
    assert gate is not None
    assert gate.completed[:3] == tuple(STANDARD_PROMPT_EVENTS[:3])


def test_resolver_env_override_pins_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONFIG-02 env probe: a registered override wins over the default 0."""
    monkeypatch.delenv(DISPATCH_RETRY_BUDGET_ENV, raising=False)
    assert int(resolve_dispatch_retry_budget()) == 0

    monkeypatch.setenv(DISPATCH_RETRY_BUDGET_ENV, "4")
    assert int(resolve_dispatch_retry_budget()) == 4

    monkeypatch.setenv(DISPATCH_RETRY_BUDGET_ENV, "not-a-number")
    assert int(resolve_dispatch_retry_budget()) == 0

    monkeypatch.setenv(DISPATCH_RETRY_BUDGET_ENV, "-1")
    assert int(resolve_dispatch_retry_budget()) == 0


def test_resolver_explicit_override_outranks_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit config value beats the env probe, but never below zero."""
    monkeypatch.setenv(DISPATCH_RETRY_BUDGET_ENV, "9")
    assert int(resolve_dispatch_retry_budget(override=2)) == 2
    assert int(resolve_dispatch_retry_budget(override=-3)) == 0
    assert int(resolve_dispatch_retry_budget(override=None)) == 9
