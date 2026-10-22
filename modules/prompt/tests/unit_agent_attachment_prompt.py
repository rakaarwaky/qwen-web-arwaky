"""Tests for agent_core_orchestrator — send_file pipeline error paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error

from modules.prompt.src.capabilities_attachment_prompt_adapter import AttachmentPromptAdapter
from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
from modules.prompt.src.capabilities_prompt_injector import PromptInjector
from modules.prompt.src.capabilities_run_cancel_registry import CapabilitiesRunCancelRegistry
from modules.shared.src import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_DOCUMENT_PARSED,
    EVENT_FILE_UPLOADED,
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SEND_CLICKED,
    EVENT_SESSION_EXPIRED,
    EVENT_WEB_LOADED,
    PIPELINE_EVENT_SEQUENCE,
    ResponseDetectionTimeoutError,
    SendDispatchError,
    StuckDetectedError,
)
from modules.shared.src.common.taxonomy_core_vo import MessageCount
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, StreamVerdict


def _make_attachment_orchestrator() -> AttachmentPromptAdapter:
    """Build an AttachmentPromptAdapter with all dependencies mocked."""
    saver = MagicMock()

    def write_output(path, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("saved output", encoding="utf-8")

    saver.write_output.side_effect = write_output
    flow = MagicMock()
    # The cut handler is the real shared policy on the flow seam (issue 9):
    # bind it so stall tests exercise the production save+verdict path.
    flow.mid_stream_cut_outcome.side_effect = PromptFlowDispatcher().mid_stream_cut_outcome
    return AttachmentPromptAdapter(
        browser=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=MagicMock(),
        saver=saver,
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        flow=flow,
        folder_adapter=MagicMock(),
        cancel=CapabilitiesRunCancelRegistry(),
    )


def _configure_lifecycle_mocks(orch) -> None:
    def navigate(_page, emitter):
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "test"})
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": "Qwen3.8-Max"})

    def upload(_page, _filepath, emitter=None, **_kwargs):
        assert emitter is not None
        emitter.emit(EVENT_FILE_UPLOADED, {"file": "test"})
        emitter.emit(EVENT_DOCUMENT_PARSED, {"file": "test"})
        return True

    def send(_page, emitter, **_kwargs):
        emitter.emit(EVENT_SEND_CLICKED, {"file": "test"})
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {"file": "test"})

    def click_send_stub(*, emitter, **_kwargs):
        send(None, emitter)
        return None

    bctx = MagicMock()
    bctx.pages = [MagicMock()]
    orch._browser.browser_session.return_value.__enter__.return_value = bctx

    orch._browser.navigate_to_chat.side_effect = navigate
    orch._uploader.upload_attachment.side_effect = lambda page, filepath, **kw: upload(
        kw.get("page"), kw.get("filepath"), emitter=kw.get("emitter")
    )
    orch._sender.count_messages.return_value = MessageCount(2)
    orch._sender.click_send.side_effect = click_send_stub


class TestSendFile:
    def test_send_click_timeout_is_sourced_from_app_config(self, tmp_path) -> None:
        """BE-4-003: the parse/send ceiling comes from AppConfig, not a
        hardcoded 120s, so QWEN_SEND_CLICK_TIMEOUT_MS can tune it."""
        from modules.shared.src.common.taxonomy_core_vo import AppConfig as VoAppConfig

        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)

        cfg = VoAppConfig(
            input_path=tmp_path / "task.md",
            output_path=tmp_path / "out.md",
            session_path=tmp_path / "session",
            send_click_timeout_ms=45_000,
        )
        orch._flow.dispatch_and_wait_for_response.side_effect = lambda **_kw: None

        captured: dict[str, object] = {}

        class _SenderConfigCapture:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)

        import modules.prompt.src.capabilities_attachment_prompt_adapter as adapter_mod

        original = adapter_mod.SenderConfig
        adapter_mod.SenderConfig = _SenderConfigCapture
        try:
            orch._execute_attachment_on_page(
                page=MagicMock(url="https://chat.qwen.ai/"),
                filepath=tmp_path / "task.md",
                att_path=tmp_path / "att.md",
                timeout_sec=60,
                active_cfg=cfg,
                emitter=MagicMock(),
                state=MagicMock(),
                prompt="hello",
            )
        finally:
            adapter_mod.SenderConfig = original

        assert captured["click_timeout_ms"] == 45_000
        assert captured["try_enter_key_fallback"] is True

    def test_send_click_timeout_defaults_to_the_documented_ceiling(self, tmp_path) -> None:
        """Without an override the ceiling stays 120s (FRD Assumptions)."""
        from modules.shared.src.common.taxonomy_core_vo import AppConfig as VoAppConfig

        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)

        cfg = VoAppConfig(
            input_path=tmp_path / "task.md",
            output_path=tmp_path / "out.md",
            session_path=tmp_path / "session",
        )
        captured: dict[str, object] = {}

        class _SenderConfigCapture:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)

        import modules.prompt.src.capabilities_attachment_prompt_adapter as adapter_mod

        original = adapter_mod.SenderConfig
        adapter_mod.SenderConfig = _SenderConfigCapture
        try:
            orch._execute_attachment_on_page(
                page=MagicMock(url="https://chat.qwen.ai/"),
                filepath=tmp_path / "task.md",
                att_path=tmp_path / "att.md",
                timeout_sec=60,
                active_cfg=cfg,
                emitter=MagicMock(),
                state=MagicMock(),
                prompt="hello",
            )
        finally:
            adapter_mod.SenderConfig = original

        assert captured["click_timeout_ms"] == 120_000

    def test_send_file_os_error(self, tmp_path):
        orch = _make_attachment_orchestrator()
        att = tmp_path / "att.md"
        att.write_text("attachment")
        result = orch.execute(
            PromptRequest(
                verb="process_prompt_with_attachment",
                prompt_file=tmp_path / "nonexistent.md",
                attachment_file=att,
                output_file=tmp_path / "out.md",
                headless=True,
            )
        )
        assert "ERROR" in str(result)

    def test_send_file_timeout_error(self, tmp_path):
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)
        orch._flow.dispatch_and_wait_for_response.side_effect = ResponseDetectionTimeoutError(
            "Response detection timeout"
        )

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        result = orch.execute(
            PromptRequest(
                verb="process_prompt_with_attachment",
                prompt_file=f,
                attachment_file=att,
                output_file=tmp_path / "out.md",
                headless=True,
            )
        )
        assert "Response detection timeout" in str(result)

    def test_send_file_delegates_to_capabilities(self, tmp_path):
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)

        def flow_stub(*, emitter, **_kwargs):
            for event in PIPELINE_EVENT_SEQUENCE[5:-1]:
                emitter.emit(event)
            return StreamVerdict(text="the response", verdict="complete")

        orch._flow.dispatch_and_wait_for_response.side_effect = flow_stub

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        result = orch.execute(
            PromptRequest(
                verb="process_prompt_with_attachment",
                prompt_file=f,
                attachment_file=att,
                output_file=tmp_path / "out.md",
                headless=True,
            )
        )
        assert "Successfully processed" in str(result.response_text)
        assert result.extraction_verdict == "complete"
        orch._flow.dispatch_and_wait_for_response.assert_called_once()
        assert orch._flow.dispatch_and_wait_for_response.call_args.kwargs["msg_count_before"] == 2

    def test_send_file_emits_session_expired_when_banner_appears_after_send(self, tmp_path):
        """When dispatch raises and the post-send banner is detected,
        EVENT_SESSION_EXPIRED is emitted with reason=post_send_banner."""
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)

        orch._flow.dispatch_and_wait_for_response.side_effect = SendDispatchError("Send failed")
        orch._browser.detect_session_expired.return_value = True

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        # Test the internal method directly since process_prompt_with_attachment
        # catches all exceptions and converts to error responses.
        with pytest.raises(SendDispatchError, match="Send failed"):
            orch._execute_attachment_on_page(
                page=MagicMock(url="https://chat.qwen.ai/"),
                filepath=f,
                att_path=att,
                timeout_sec=30,
                active_cfg=MagicMock(),
                emitter=MagicMock(),
                state=MagicMock(),
                prompt="hello",
            )

        orch._browser.detect_session_expired.assert_called_once()
        # Check that the emitter was called with EVENT_SESSION_EXPIRED
        # The emitter used in the internal call is a MagicMock
        emitter = orch._flow.dispatch_and_wait_for_response.call_args.kwargs.get("emitter")
        if emitter:
            emit_calls = [c for c in emitter.emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
            assert len(emit_calls) == 1
            assert emit_calls[0].args[1] == {"url": "https://chat.qwen.ai/", "reason": "post_send_banner"}

    def test_send_file_no_session_expired_emit_when_clean(self, tmp_path):
        """When dispatch raises but no banner is detected, EVENT_SESSION_EXPIRED is not emitted."""
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)

        orch._flow.dispatch_and_wait_for_response.side_effect = SendDispatchError("Send failed")
        orch._browser.detect_session_expired.return_value = False

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        # Test the internal method directly since process_prompt_with_attachment
        # catches all exceptions and converts to error responses.
        with pytest.raises(SendDispatchError, match="Send failed"):
            orch._execute_attachment_on_page(
                page=MagicMock(url="https://chat.qwen.ai/"),
                filepath=f,
                att_path=att,
                timeout_sec=30,
                active_cfg=MagicMock(),
                emitter=MagicMock(),
                state=MagicMock(),
                prompt="hello",
            )

        orch._browser.detect_session_expired.assert_called_once()
        emitter = orch._flow.dispatch_and_wait_for_response.call_args.kwargs.get("emitter")
        if emitter:
            emit_calls = [c for c in emitter.emit.call_args_list if c.args[0] == EVENT_SESSION_EXPIRED]
            assert len(emit_calls) == 0

    def test_inject_text_types_with_delay_fallback(self):
        """Slow typing is delegated to inject_text's type() fallback."""
        page = MagicMock()
        page.evaluate.return_value = False
        el = MagicMock()
        el.fill.side_effect = Error("fill failed")
        injector = PromptInjector()
        with (
            patch.object(PromptInjector, "find_input", return_value=el),
            patch.object(PromptInjector, "_verify_injection", return_value=True),
        ):
            injector.inject_text(page, "text")
        el.type.assert_called_once_with("text", delay=10)

    def test_stalled_stream_reports_stalled_and_saves_the_partial_from_the_dom(self, tmp_path):
        """BE-1-003 / FRD "A response file survives a mid-stream extraction failure".

        Attachment pipeline: a stall reached through ``execute()`` yields
        ``extraction_verdict == "stalled"`` and persists the partial answer.
        The exception carries no ``partial_text`` here, so the adapter's DOM
        fallback supplies the cut text from the live page — both partial-text
        sources are pinned by the file/attachment pair.
        """
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)
        orch._browser.detect_session_expired.return_value = False
        orch._folder_adapter.resolve_to_attachment.side_effect = lambda p: p

        partial = "Operating margin improved by 3 points, driven by lower cloud spend."

        # The live page still holds the cut text (first-poll cut: the monitor
        # confirmed no forward text of its own before the stall fired).
        page = MagicMock()
        page.evaluate.return_value = partial
        bctx = orch._browser.browser_session.return_value.__enter__.return_value
        bctx.pages = [page]

        def write_output(path, text, *_args, **_kwargs):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(text), encoding="utf-8")

        orch._saver.write_output.side_effect = write_output

        def raise_stuck(*_args, **_kwargs):
            # Raised (not returned) so the real mid-stream error path runs.
            raise StuckDetectedError("Stuck detected: no forward lifecycle event for 300s")

        orch._flow.dispatch_and_wait_for_response.side_effect = raise_stuck

        prompt = tmp_path / "task.md"
        prompt.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")
        out_file = tmp_path / "out.md"

        result = orch.execute(
            PromptRequest(
                verb="process_prompt_with_attachment",
                prompt_file=prompt,
                attachment_file=att,
                output_file=out_file,
                headless=True,
            )
        )

        assert result.extraction_verdict == "stalled"
        assert "Stuck detected" in str(result.response_text)
        assert "Successfully processed" not in str(result.response_text), "a stall must not read as success"
        assert out_file.name in str(result.response_text), (
            "the cut response must name the saved partial artifact (FR-PROMPT-003 Output row)"
        )
        assert out_file.is_file(), "the partial response artifact must survive the stall"
        assert partial in out_file.read_text(encoding="utf-8")
        assert page.evaluate.called, "the DOM fallback must read the cut text off the live page"
