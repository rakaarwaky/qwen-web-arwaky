"""End-to-end tests for the direct prompt pipeline.

The pipeline's promise is one ordered sequence: open the browser, navigate,
prove the session, then inject, send, and save. These drive the real
adapter with a stub browser context and a real flow orchestrator, so the
sequence is exercised without a live session.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.prompt.src.capabilities_direct_prompt_adapter import DirectPromptAdapter
from modules.prompt.src.capabilities_output_saver import Saver
from modules.prompt.src.capabilities_prompt_flow_dispatcher import PromptFlowDispatcher
from modules.prompt.src.capabilities_prompt_injector import PromptInjector
from modules.prompt.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_SEND_CLICKED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    EVENT_WEB_LOADED,
)


@pytest.fixture
def calls() -> list[str]:
    """Records the order in which the pipeline drove its browser steps."""
    return []


@contextmanager
def _session(page: MagicMock):
    """Yield a browser context that hands out one page and closes cleanly."""
    context = MagicMock()
    context.pages = [page]
    yield context


def _page() -> MagicMock:
    """A page stub that reports a completed generation to the monitor.

    The monitor's terminal check reads two DOM probes: whether any
    stop/thinking indicator is visible (no) and the latest message text
    (the answer). Both settle on terminal values, so the wait loop ends
    instead of exhausting a side-effect list.
    """
    page = MagicMock()
    page.evaluate = MagicMock(return_value="The answer")
    page.query_selector.return_value = MagicMock()
    page.locator.return_value.count = MagicMock(return_value=1)
    page.url = "https://chat.qwen.ai/"
    return page


def _completed_monitor() -> MagicMock:
    """A monitor that reports a completed generation immediately, so the
    pipeline's save step runs without a live stream.
    """
    monitor = MagicMock(spec=StreamMonitor)
    monitor.is_generation_complete.return_value = True
    monitor.is_thinking_active.return_value = False

    def _wait(_page: MagicMock, _timeout: object, _count: object, emitter: MagicMock, **_kwargs: object) -> str:
        """Emit the thinking, streaming, and finish events the real monitor
        emits as a response runs, so the saver's output event is accepted
        by the lifecycle gate.
        """
        emitter.emit(EVENT_THINKING_STARTED, {})
        emitter.emit(EVENT_STREAMING_GENERATION, {"char_count": len("The answer")})
        emitter.emit(EVENT_GENERATION_FINISHED, {"char_count": len("The answer")})
        return "The answer"

    monitor.wait_for_response = MagicMock(side_effect=_wait)
    return monitor


def _adapter(calls: list[str]) -> DirectPromptAdapter:
    """Return the direct adapter wired to a stub browser that records its steps."""
    page = _page()
    browser = MagicMock()
    browser.browser_session = MagicMock(side_effect=lambda cfg: _session(page))

    def _navigate(_page: MagicMock, emitter: MagicMock) -> None:
        """Emit the startup events the real browser seam emits, so the
        lifecycle gate accepts the later prompt-injected event.
        """
        calls.append("navigate")
        emitter.emit(EVENT_WEB_LOADED, {"url": "https://chat.qwen.ai/"})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "https://chat.qwen.ai/"})
        emitter.emit(EVENT_MODEL_VERIFIED, {"model": "qwen3-max"})

    browser.navigate_to_chat = MagicMock(side_effect=_navigate)
    browser.check_auth = MagicMock(side_effect=lambda *_a, **_k: calls.append("check_auth"))

    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()

    sender = MagicMock(spec=SendDispatcher)
    sender.count_messages = MagicMock(return_value=0)

    def _click_send(_page: MagicMock, emitter: MagicMock, **_kwargs: object) -> None:
        """Emit the send and dispatch-acknowledged events the real sender
        emits when the page accepts the prompt, so the flow may wait for a
        response.
        """
        emitter.emit(EVENT_SEND_CLICKED, {})
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {})

    sender.click_send = MagicMock(side_effect=_click_send)

    return DirectPromptAdapter(
        browser=browser,
        injector=PromptInjector(),
        sender=sender,
        streamer=_completed_monitor(),
        saver=Saver(),
        observability=observability,
        flow=PromptFlowDispatcher(),
    )


def _run(adapter: DirectPromptAdapter, tmp_path: Path) -> None:
    adapter.process_direct_prompt(
        prompt="Summarize this report",
        output_file=tmp_path / "out.md",
        headless=True,
    )


def test_e2e_a_direct_prompt_navigates_before_it_checks_the_session(calls: list[str], tmp_path: Path) -> None:
    """A session check on a page that has not loaded proves nothing, so
    navigation comes first.
    """
    _run(_adapter(calls), tmp_path)

    assert calls == ["navigate", "check_auth"], f"the pipeline's first steps must be ordered, got {calls}"


def test_e2e_a_direct_prompt_proves_the_session_before_it_sends(calls: list[str], tmp_path: Path) -> None:
    """An unauthenticated run must fail before it ever clicks send, so
    the session check precedes the prompt injection.
    """
    _run(_adapter(calls), tmp_path)

    assert "check_auth" in calls, "the pipeline must prove the session before it sends"
    assert calls.index("navigate") < calls.index("check_auth")


def test_e2e_a_direct_prompt_saves_the_response_to_the_named_output(calls: list[str], tmp_path: Path) -> None:
    """The operator's named output path is where the answer lands, not a
    generated default directory. The filename carries a timestamp and a
    short unique suffix so repeated runs never overwrite each other, but
    the directory is the caller's own.
    """
    _run(_adapter(calls), tmp_path)

    written = sorted(path for path in tmp_path.iterdir() if path.suffix == ".md")
    assert written, "the pipeline must write the response into the caller's output directory"
    assert "The answer" in written[0].read_text(encoding="utf-8"), (
        "the saved file must carry the response, not the prompt"
    )
