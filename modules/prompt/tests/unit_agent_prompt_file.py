"""Unit tests for PromptFileAdapter (AES405)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.prompt.src.capabilities_prompt_file_adapter import PromptFileAdapter
from modules.shared.src.taxonomy_core_error import SendDispatchError
from modules.shared.src.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SESSION_EXPIRED,
    EVENT_WEB_LOADED,
    STANDARD_PROMPT_EVENTS,
)
from modules.shared.src.taxonomy_core_vo import MessageCount


def _browser_stub(emitter_events: tuple = ()) -> MagicMock:
    """A browser mock whose navigate_to_chat emits the page-phase lifecycle events."""
    bctx = MagicMock()
    bctx.pages = [MagicMock()]

    def navigate_to_chat(_page, emitter):
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "test"})
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": "Qwen3.8-Max"})

    browser = MagicMock()
    browser.browser_session.return_value.__enter__.return_value = bctx
    browser.navigate_to_chat.side_effect = navigate_to_chat
    return browser


def _make_file_orchestrator() -> tuple[PromptFileAdapter, dict[str, MagicMock]]:
    browser = _browser_stub()
    injector = MagicMock()
    sender = MagicMock()
    sender.count_messages.return_value = MessageCount(2)
    streamer = MagicMock()
    saver = MagicMock()

    def write_output(path, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("saved output", encoding="utf-8")

    saver.write_output.side_effect = write_output
    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()

    flow = MagicMock()
    cancel = MagicMock()
    cancel.register = MagicMock()
    cancel.release = MagicMock()
    cancel.set_active_bctx = MagicMock()
    cancel.cancel_by_event = MagicMock()

    orchestrator = PromptFileAdapter(
        browser=browser,
        injector=injector,
        sender=sender,
        streamer=streamer,
        saver=saver,
        observability=observability,
        flow=flow,
        cancel=cancel,
    )
    mocks = {
        "browser": browser,
        "injector": injector,
        "sender": sender,
        "streamer": streamer,
        "saver": saver,
        "observability": observability,
        "flow": flow,
        "cancel": cancel,
        "emitter": MagicMock(),
    }
    return orchestrator, mocks


def test_process_prompt_file_only_happy_path(tmp_path) -> None:
    orch, mocks = _make_file_orchestrator()

    def flow_stub(*, emitter, **_kwargs):
        for event in STANDARD_PROMPT_EVENTS[3:-1]:
            emitter.emit(event)
        return "Hello from Qwen AI!"

    mocks["flow"].dispatch_and_wait_for_response.side_effect = flow_stub

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Test prompt")

    response = orch.process_prompt_file_only(prompt_file, headless=True)

    assert "Successfully processed" in str(response)
    mocks["flow"].dispatch_and_wait_for_response.assert_called_once()


def test_process_prompt_file_only_emits_session_expired_when_banner_appears_after_send() -> None:
    """When dispatch raises and the post-send banner is detected,
    EVENT_SESSION_EXPIRED is emitted with reason=post_send_banner."""
    orch, mocks = _make_file_orchestrator()

    mocks["flow"].dispatch_and_wait_for_response.side_effect = SendDispatchError("Send failed")

    # Mock the browser to return True for detect_session_expired
    mocks["browser"].detect_session_expired.return_value = True

    with pytest.raises(SendDispatchError, match="Send failed"):
        orch._execute_file_on_page(
            page=MagicMock(url="https://chat.qwen.ai/"),
            filepath=MagicMock(),
            timeout_sec=30,
            active_cfg=MagicMock(),
            emitter=mocks["emitter"],
            state=MagicMock(),
        )

    mocks["browser"].detect_session_expired.assert_called_once()
    emit_calls = [c for c in mocks["emitter"].emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
    assert len(emit_calls) == 1
    assert emit_calls[0].args[1] == {"url": "https://chat.qwen.ai/", "reason": "post_send_banner"}


def test_process_prompt_file_only_no_session_expired_emit_when_clean() -> None:
    """When dispatch raises but no banner is detected, EVENT_SESSION_EXPIRED is not emitted."""
    orch, mocks = _make_file_orchestrator()

    mocks["flow"].dispatch_and_wait_for_response.side_effect = SendDispatchError("Send failed")

    # Mock the browser to return False for detect_session_expired
    mocks["browser"].detect_session_expired.return_value = False

    with pytest.raises(SendDispatchError, match="Send failed"):
        orch._execute_file_on_page(
            page=MagicMock(url="https://chat.qwen.ai/"),
            filepath=MagicMock(),
            timeout_sec=30,
            active_cfg=MagicMock(),
            emitter=mocks["emitter"],
            state=MagicMock(),
        )

    mocks["browser"].detect_session_expired.assert_called_once()
    emit_calls = [c for c in mocks["emitter"].emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
    assert len(emit_calls) == 0
