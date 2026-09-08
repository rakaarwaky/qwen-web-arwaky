"""Tests for agent_core_orchestrator — send_file pipeline error paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from playwright.sync_api import Error

from modules.core.src.agent_attachment_prompt_orchestrator import AttachmentPromptOrchestrator
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.shared.src import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_DOCUMENT_PARSED,
    EVENT_FILE_UPLOADED,
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SEND_CLICKED,
    EVENT_WEB_LOADED,
    PIPELINE_EVENT_SEQUENCE,
    ResponseDetectionTimeoutError,
)


def _make_attachment_orchestrator() -> AttachmentPromptOrchestrator:
    """Build an AttachmentPromptOrchestrator with all dependencies mocked."""
    saver = MagicMock()

    def write_output(path, *_args, **_kwargs):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("saved output", encoding="utf-8")

    saver.write_output.side_effect = write_output
    return AttachmentPromptOrchestrator(
        browser=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=MagicMock(),
        saver=saver,
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        flow=MagicMock(),
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

    orch._browser.navigate_to_chat.side_effect = navigate
    orch._browser.browser_session.return_value.__enter__.return_value.pages = [MagicMock()]
    orch._uploader.upload_attachment.side_effect = upload
    orch._sender.click_send.side_effect = send


class TestSendFile:
    def test_send_file_os_error(self, tmp_path):
        orch = _make_attachment_orchestrator()
        att = tmp_path / "att.md"
        att.write_text("attachment")
        result = orch.process_prompt_with_attachment(
            prompt_file=tmp_path / "nonexistent.md",
            attachment_file=att,
            output_file=tmp_path / "out.md",
            headless=True,
        )
        assert "ERROR" in str(result)

    def test_send_file_timeout_error(self, tmp_path):
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)
        orch._sender.count_messages.return_value = 0
        orch._uploader.upload_attachment.return_value = True
        orch._flow.dispatch_and_wait_for_response.side_effect = ResponseDetectionTimeoutError(
            "Response detection timeout"
        )

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        result = orch.process_prompt_with_attachment(
            prompt_file=f,
            attachment_file=att,
            output_file=tmp_path / "out.md",
            headless=True,
        )
        assert "Response detection timeout" in str(result)

    def test_send_file_delegates_to_capabilities(self, tmp_path):
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)
        orch._sender.count_messages.return_value = 2
        orch._uploader.upload_attachment.return_value = True

        def flow_stub(*, emitter, **_kwargs):
            for event in PIPELINE_EVENT_SEQUENCE[5:-1]:
                emitter.emit(event)
            return "the response"

        orch._flow.dispatch_and_wait_for_response.side_effect = flow_stub

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        result = orch.process_prompt_with_attachment(
            prompt_file=f,
            attachment_file=att,
            output_file=tmp_path / "out.md",
            headless=True,
        )
        assert "Successfully processed" in str(result)
        orch._flow.dispatch_and_wait_for_response.assert_called_once()
        assert orch._flow.dispatch_and_wait_for_response.call_args.kwargs["msg_count_before"] == 2

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
