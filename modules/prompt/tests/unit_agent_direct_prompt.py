"""Unit tests for DirectPromptAdapter (AES405)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.prompt.src.capabilities_direct_prompt_adapter import DirectPromptAdapter
from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
from modules.shared.src.common.taxonomy_core_constant import DEFAULT_OUTPUT, DIRECT_PROMPT_STEM
from modules.shared.src.common.taxonomy_core_error import ResponseDetectionTimeoutError, SendDispatchError
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SEND_CLICKED,
    EVENT_SESSION_EXPIRED,
    EVENT_WEB_LOADED,
    STANDARD_PROMPT_EVENTS,
)
from modules.shared.src.common.taxonomy_core_vo import MessageCount
from modules.shared.src.prompt.taxonomy_prompt_vo import StreamVerdict


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


def _make_direct_orchestrator() -> tuple[DirectPromptAdapter, dict[str, MagicMock]]:
    browser_lifecycle = MagicMock()
    browser_diagnostics = MagicMock()
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
    # The cut handler is the real shared policy on the flow seam (issue 9):
    # bind it so timeout/cut tests exercise the production save+verdict path.
    flow.mid_stream_cut_outcome.side_effect = PromptFlowDispatcher().mid_stream_cut_outcome
    orchestrator = DirectPromptAdapter(
        browser_lifecycle=browser_lifecycle,
        browser_navigation=browser,
        browser_diagnostics=browser_diagnostics,
        injector=injector,
        sender=sender,
        streamer=streamer,
        saver=saver,
        observability=observability,
        flow=flow,
    )
    mocks = {
        "browser_lifecycle": browser_lifecycle,
        "browser_navigation": browser,
        "browser_diagnostics": browser_diagnostics,
        "injector": injector,
        "sender": sender,
        "streamer": streamer,
        "saver": saver,
        "observability": observability,
        "flow": flow,
        "emitter": MagicMock(),
    }
    return orchestrator, mocks


def test_process_direct_prompt_happy_path() -> None:
    orch, mocks = _make_direct_orchestrator()

    def flow_stub(*, emitter, **_kwargs):
        for event in STANDARD_PROMPT_EVENTS[3:-1]:
            emitter.emit(event)
        return StreamVerdict(text="Hello from Qwen AI!", verdict="complete")

    mocks["flow"].dispatch_and_wait_for_response.side_effect = flow_stub

    response = orch.process_direct_prompt("What is Python?", timeout_sec=30, headless=True)

    assert "Successfully processed" in str(response.response_text)
    assert response.extraction_verdict == "complete"
    mocks["flow"].dispatch_and_wait_for_response.assert_called_once()
    assert mocks["flow"].dispatch_and_wait_for_response.call_args.kwargs["prompt"] == "What is Python?"
    saved_path = mocks["saver"].write_output.call_args.args[0]
    assert saved_path.parent == DEFAULT_OUTPUT
    assert saved_path.name.startswith(f"{DIRECT_PROMPT_STEM}_")
    assert not saved_path.name.startswith("tmp")


def test_process_direct_prompt_timeout_error() -> None:
    orch, mocks = _make_direct_orchestrator()

    def click_send_stub(*, emitter, **_kwargs):
        emitter.emit(EVENT_SEND_CLICKED)
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED)
        return None

    mocks["sender"].click_send.side_effect = click_send_stub
    mocks["flow"].dispatch_and_wait_for_response.side_effect = ResponseDetectionTimeoutError(
        "Timeout waiting for response"
    )

    response = orch.process_direct_prompt("Test prompt", timeout_sec=10)

    assert "Timeout waiting for response" in str(response)
    assert "no partial response available to save" in str(response)


def test_process_direct_prompt_emits_session_expired_when_banner_appears_after_send() -> None:
    """When dispatch raises and the post-send banner is detected,
    EVENT_SESSION_EXPIRED is emitted with reason=post_send_banner."""
    orch, mocks = _make_direct_orchestrator()

    mocks["flow"].dispatch_and_wait_for_response.side_effect = SendDispatchError("Send failed")

    # Mock the browser to return True for detect_session_expired
    mocks["browser_diagnostics"].detect_session_expired.return_value = True

    with pytest.raises(SendDispatchError, match="Send failed"):
        orch._execute_direct_on_page(
            page=MagicMock(url="https://chat.qwen.ai/"),
            filepath=MagicMock(),
            prompt="Test prompt",
            timeout_sec=30,
            active_cfg=MagicMock(),
            emitter=mocks["emitter"],
            state=MagicMock(),
        )

    mocks["browser_diagnostics"].detect_session_expired.assert_called_once()
    # The emitter emit should have been called with EVENT_SESSION_EXPIRED
    emit_calls = [c for c in mocks["emitter"].emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
    assert len(emit_calls) == 1
    assert emit_calls[0].args[1] == {"url": "https://chat.qwen.ai/", "reason": "post_send_banner"}


def test_process_direct_prompt_no_session_expired_emit_when_clean() -> None:
    """When dispatch raises but no banner is detected, EVENT_SESSION_EXPIRED is not emitted."""
    orch, mocks = _make_direct_orchestrator()

    mocks["flow"].dispatch_and_wait_for_response.side_effect = SendDispatchError("Send failed")

    # Mock the browser to return False for detect_session_expired
    mocks["browser_diagnostics"].detect_session_expired.return_value = False

    with pytest.raises(SendDispatchError, match="Send failed"):
        orch._execute_direct_on_page(
            page=MagicMock(url="https://chat.qwen.ai/"),
            filepath=MagicMock(),
            prompt="Test prompt",
            timeout_sec=30,
            active_cfg=MagicMock(),
            emitter=mocks["emitter"],
            state=MagicMock(),
        )

    mocks["browser_diagnostics"].detect_session_expired.assert_called_once()
    emit_calls = [c for c in mocks["emitter"].emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
    assert len(emit_calls) == 0


class TestDirectPromptSessionResolver:
    """Pool session selection must reach the direct pipeline (single-member pool included)."""

    def test_resolver_session_reaches_the_browser_session(self) -> None:
        orch, mocks = _make_direct_orchestrator()
        pool_path = Path("/home/raka/.qwen-web-arwaky/sessions/session_1")

        def flow_stub(*, active_cfg, **_kwargs):
            assert active_cfg.session_path == pool_path
            return "ok"

        mocks["flow"].dispatch_and_wait_for_response.side_effect = flow_stub

        orch.process_direct_prompt(
            "What is Python?",
            session_resolver=lambda: pool_path,
            output_file=Path("/tmp/direct_resolver_out.md"),
        )

        cfg_arg = mocks["browser_lifecycle"].browser_session.call_args.args[0]
        assert cfg_arg.session_path == pool_path

    def test_resolver_returning_none_falls_back_to_the_default_session(self) -> None:
        from modules.shared.src.common.taxonomy_core_constant import DEFAULT_SESSION

        orch, mocks = _make_direct_orchestrator()
        mocks["flow"].dispatch_and_wait_for_response.side_effect = lambda **_: "ok"

        orch.process_direct_prompt(
            "What is Python?",
            session_resolver=lambda: None,
            output_file=Path("/tmp/direct_resolver_none.md"),
        )

        cfg_arg = mocks["browser_lifecycle"].browser_session.call_args.args[0]
        assert cfg_arg.session_path == DEFAULT_SESSION

    def test_resolver_reraising_reports_no_session(self) -> None:
        from modules.shared.src.common.taxonomy_core_constant import DEFAULT_SESSION

        orch, mocks = _make_direct_orchestrator()
        mocks["flow"].dispatch_and_wait_for_response.side_effect = lambda **_: "ok"

        def failing_resolver() -> Path | None:
            raise RuntimeError("pool read failed")

        orch.process_direct_prompt(
            "What is Python?",
            session_resolver=failing_resolver,
            output_file=Path("/tmp/direct_resolver_fail.md"),
        )

        cfg_arg = mocks["browser_lifecycle"].browser_session.call_args.args[0]
        assert cfg_arg.session_path == DEFAULT_SESSION
