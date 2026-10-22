"""Unit tests for PromptFileAdapter (AES405)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.prompt.src.capabilities_prompt_file_adapter import PromptFileAdapter
from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
from modules.shared.src.common.taxonomy_core_error import (
    ResponseDetectionTimeoutError,
    SendDispatchError,
    StuckDetectedError,
)
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SESSION_EXPIRED,
    EVENT_WEB_LOADED,
    STANDARD_PROMPT_EVENTS,
)
from modules.shared.src.common.taxonomy_core_vo import MessageCount
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, StreamVerdict


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
    # The cut handler is the real shared policy on the flow seam (issue 9):
    # bind it so stall/timeout tests exercise the production save+verdict path.
    flow.mid_stream_cut_outcome.side_effect = PromptFlowDispatcher().mid_stream_cut_outcome
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
        return StreamVerdict(text="Hello from Qwen AI!", verdict="complete")

    mocks["flow"].dispatch_and_wait_for_response.side_effect = flow_stub

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Test prompt")

    response = orch.process_prompt_file_only(prompt_file, headless=True)

    assert "Successfully processed" in str(response.response_text)
    assert response.extraction_verdict == "complete"
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
            prompt="hello",
        )

    mocks["browser"].detect_session_expired.assert_called_once()
    emit_calls = [c for c in mocks["emitter"].emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
    assert len(emit_calls) == 1
    assert emit_calls[0].args[1] == {"url": "https://chat.qwen.ai/", "reason": "post_send_banner"}


def test_process_prompt_file_only_reads_the_prompt_file_before_browser_launch(tmp_path) -> None:
    """BE-3-001 / FR-PROMPT-002: a nonexistent prompt file fails at pre-flight,
    before the browser session is ever entered."""
    from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry

    browser = MagicMock()
    browser.browser_session.return_value.__enter__.return_value = MagicMock(pages=[MagicMock()])

    class _EntryPoint(MagicMock):
        pass

    adapter = PromptFileAdapter(
        browser=browser,
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        flow=MagicMock(),
        cancel=CapabilitiesRunCancelRegistry(),
    )

    result = adapter.process_prompt_file_only(tmp_path / "never-existed.md", headless=True)

    assert "not found" in str(result.response_text).lower(), (
        f"a missing prompt file must report a file error naming the path, got {result}"
    )
    browser.browser_session.assert_not_called()
    adapter._flow.dispatch_and_wait_for_response.assert_not_called()
    # No extraction was attempted, so no verdict is claimed (BE-1-003).
    assert result.extraction_verdict is None


def test_process_prompt_file_only_reports_an_unreadable_prompt_file_before_browser_launch(tmp_path) -> None:
    """BE-3-001: an unreadable prompt file fails with a file error naming the path."""
    import os

    from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry

    prompt_file = tmp_path / "unreadable.md"
    prompt_file.write_text("prompt")
    prompt_file.chmod(0o000)
    if os.name == "nt" or os.geteuid() == 0:
        import pytest as _pytest

        _pytest.skip("chmod 0o000 does not block reads as root or on Windows")

    browser = MagicMock()

    adapter = PromptFileAdapter(
        browser=browser,
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        flow=MagicMock(),
        cancel=CapabilitiesRunCancelRegistry(),
    )

    result = adapter.process_prompt_file_only(prompt_file, headless=True)

    assert "ERROR" in str(result.response_text), f"an unreadable file must surface an error, got {result}"
    assert str(prompt_file) in str(result.response_text)
    browser.browser_session.assert_not_called()


def test_process_prompt_file_only_pre_flight_matches_the_attachment_adapter(tmp_path) -> None:
    """BE-3-001 parity: the file and attachment adapters both reject a bad
    prompt path before any browser work, in the same position."""
    from modules.prompt.src.capabilities_attachment_prompt_adapter import AttachmentPromptAdapter
    from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry

    attachment = tmp_path / "att.md"
    attachment.write_text("attachment")

    file_adapter = PromptFileAdapter(
        browser=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        flow=MagicMock(),
        cancel=CapabilitiesRunCancelRegistry(),
    )
    attachment_adapter = AttachmentPromptAdapter(
        browser=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        flow=MagicMock(),
        folder_adapter=MagicMock(),
        cancel=CapabilitiesRunCancelRegistry(),
    )

    file_result = file_adapter.process_prompt_file_only(tmp_path / "absent.md", headless=True)
    attachment_result = attachment_adapter.process_prompt_with_attachment(
        prompt_file=tmp_path / "absent.md",
        attachment_file=attachment,
        output_file=tmp_path / "out.md",
        headless=True,
    )

    assert "not found" in str(file_result.response_text).lower()
    assert "not found" in str(attachment_result.response_text).lower()
    file_adapter._browser.browser_session.assert_not_called()
    attachment_adapter._browser.browser_session.assert_not_called()


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
            prompt="hello",
        )

    mocks["browser"].detect_session_expired.assert_called_once()
    emit_calls = [c for c in mocks["emitter"].emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
    assert len(emit_calls) == 0


# ─── BE-1-003: mid-stream cuts keep an honest verdict and the artifact ──────


def _real_content_saver(mocks: dict) -> None:
    """Make the mocked saver persist the REAL text it is handed."""

    def write_output(path, text, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(text), encoding="utf-8")

    mocks["saver"].write_output.side_effect = write_output


def test_stalled_stream_saves_the_partial_artifact_with_a_stalled_verdict(tmp_path) -> None:
    """BE-1-003 AC2 / FRD "A response file survives a mid-stream extraction failure".

    A stalled stream must reach PromptResponse with
    ``extraction_verdict == "stalled"`` AND leave the partial response file
    on disk — not a silent success string and not a verdict-less error.
    """
    orch, mocks = _make_file_orchestrator()
    _real_content_saver(mocks)
    mocks["browser"].detect_session_expired.return_value = False

    partial = "Revenue grew 12% quarter over quarter, driven by"

    def raise_stuck(*_args, **_kwargs):
        # side_effect raises (not returns) so the real error path runs; the
        # monitor carries its last observed text on the exception in production.
        raise StuckDetectedError(
            "Stuck detected: no forward lifecycle event (thinking/streaming/completion) for 300s",
            partial_text=partial,
        )

    mocks["flow"].dispatch_and_wait_for_response.side_effect = raise_stuck

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Summarize the quarterly report")
    out_file = tmp_path / "out.md"

    response = orch.execute(
        PromptRequest(
            verb="process_prompt_file_only",
            prompt_file=prompt_file,
            output_file=out_file,
            headless=True,
        )
    )

    assert response.extraction_verdict == "stalled"
    assert "Stuck detected" in str(response.response_text)
    assert "Successfully processed" not in str(response.response_text), "a stall must not read as success"
    assert out_file.name in str(response.response_text), (
        "the cut response must name the saved partial artifact (FR-PROMPT-001 Output row)"
    )
    assert out_file.is_file(), "the partial response artifact must survive the stall"
    assert partial in out_file.read_text(encoding="utf-8")


def test_timed_out_stream_saves_the_partial_artifact_with_an_incomplete_verdict(tmp_path) -> None:
    """BE-1-003: a hard timeout cut is ``incomplete`` — extraction ran but
    never reached a terminal event — and its partial text is still saved."""
    orch, mocks = _make_file_orchestrator()
    _real_content_saver(mocks)
    mocks["browser"].detect_session_expired.return_value = False

    partial = "Operating margin improved by 3 points,"

    def raise_timeout(*_args, **_kwargs):
        raise ResponseDetectionTimeoutError(
            "Response hard timeout: 5s elapsed exceeds the 5s cutoff without a terminal generation event",
            partial_text=partial,
        )

    mocks["flow"].dispatch_and_wait_for_response.side_effect = raise_timeout

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Summarize the quarterly report")
    out_file = tmp_path / "out.md"

    response = orch.execute(
        PromptRequest(
            verb="process_prompt_file_only",
            prompt_file=prompt_file,
            output_file=out_file,
            headless=True,
        )
    )

    assert response.extraction_verdict == "incomplete"
    assert "timeout" in str(response.response_text).lower()
    assert out_file.name in str(response.response_text), (
        "the cut response must name the saved partial artifact (FR-PROMPT-002 Output row)"
    )
    assert out_file.is_file(), "the partial response artifact must survive the cut"
    assert partial in out_file.read_text(encoding="utf-8")


def test_a_cancel_still_reports_no_extraction_verdict(tmp_path) -> None:
    """BE-1-003 guard: ``None`` stays reserved for no-extraction outcomes —
    a cancel during the wait must not claim stalled/incomplete/complete."""
    from modules.shared.src.common.taxonomy_core_error import RunCancelledError

    orch, mocks = _make_file_orchestrator()
    mocks["browser"].detect_session_expired.return_value = False

    def raise_cancelled(*_args, **_kwargs):
        raise RunCancelledError("Cancelled by user while waiting for response")

    mocks["flow"].dispatch_and_wait_for_response.side_effect = raise_cancelled

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Summarize the quarterly report")

    response = orch.execute(
        PromptRequest(
            verb="process_prompt_file_only",
            prompt_file=prompt_file,
            output_file=tmp_path / "out.md",
            headless=True,
        )
    )

    assert response.extraction_verdict is None
    assert "Cancelled" in str(response.response_text)
