"""Unit tests for DirectPromptOrchestrator (AES405)."""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator
from modules.shared.src.taxonomy_core_error import ResponseDetectionTimeoutError
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SEND_CLICKED,
    EVENT_WEB_LOADED,
    STANDARD_PROMPT_EVENTS,
)


def _make_direct_orchestrator() -> tuple[DirectPromptOrchestrator, dict[str, MagicMock]]:
    browser = MagicMock()
    injector = MagicMock()
    sender = MagicMock()
    streamer = MagicMock()
    saver = MagicMock()

    def write_output(path, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("saved output", encoding="utf-8")

    saver.write_output.side_effect = write_output
    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()

    orchestrator = DirectPromptOrchestrator(
        browser=browser,
        injector=injector,
        sender=sender,
        streamer=streamer,
        saver=saver,
        observability=observability,
        flow=MagicMock(),
    )
    mocks = {
        "browser": browser,
        "injector": injector,
        "sender": sender,
        "streamer": streamer,
        "saver": saver,
        "observability": observability,
        "flow": orchestrator._flow,
    }
    return orchestrator, mocks


def test_process_direct_prompt_happy_path() -> None:
    orch, mocks = _make_direct_orchestrator()

    page = MagicMock()
    page.url = "https://chat.qwen.ai/"
    bctx = MagicMock()
    bctx.pages = [page]
    mocks["browser"].browser_session.return_value.__enter__.return_value = bctx

    def navigate_stub(_page, emitter):
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "test"})
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": "Qwen3.8-Max"})

    mocks["browser"].navigate_to_chat.side_effect = navigate_stub

    def flow_stub(*, emitter, **_kwargs):
        for event in STANDARD_PROMPT_EVENTS[3:-1]:
            emitter.emit(event)
        return "Hello from Qwen AI!"

    mocks["flow"].dispatch_and_wait_for_response.side_effect = flow_stub

    response = orch.process_direct_prompt("What is Python?", timeout_sec=30, headless=True)

    assert str(response) == "Hello from Qwen AI!"
    mocks["flow"].dispatch_and_wait_for_response.assert_called_once()
    assert mocks["flow"].dispatch_and_wait_for_response.call_args.kwargs["prompt"] == "What is Python?"


def test_process_direct_prompt_timeout_error() -> None:
    orch, mocks = _make_direct_orchestrator()

    page = MagicMock()
    bctx = MagicMock()
    bctx.pages = [page]
    mocks["browser"].browser_session.return_value.__enter__.return_value = bctx

    def navigate_stub(_p, emitter):
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "test"})
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": "Qwen3.8-Max"})

    mocks["browser"].navigate_to_chat.side_effect = navigate_stub

    def send_stub(_p, emitter, **_kwargs):
        emitter.emit(EVENT_SEND_CLICKED)
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED)

    mocks["sender"].click_send.side_effect = send_stub
    mocks["streamer"].wait_for_response.side_effect = ResponseDetectionTimeoutError("Timeout waiting for response")
    mocks["flow"].dispatch_and_wait_for_response.side_effect = ResponseDetectionTimeoutError(
        "Timeout waiting for response"
    )

    response = orch.process_direct_prompt("Test prompt", timeout_sec=10)

    assert "Timeout waiting for response" in str(response)
