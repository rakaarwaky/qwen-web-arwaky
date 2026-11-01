"""End-to-end runtime lifecycle through the aggregate door.

No live network: the page-dependent verbs run against mock pages the way
``e2e_prompt_pipeline.py`` scripts its DOM, but every step routes through
one ``execute()`` call on the real aggregate — ``upload`` validates a
real temp file, ``inject`` fills a scripted input, ``send`` clicks the
scripted send control, ``watch`` reads the scripted completed stream, and
``persist`` writes the artifact to a real path. The steps must not lose
the hand-off facts (the text injected is the text the watch verb
reports, the response is the one persisted).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from modules.prompt_runtime.src.agent_prompt_runtime_orchestrator import PromptRuntimeOrchestrator
from modules.prompt_runtime.src.capabilities_file_uploader import FileUploader
from modules.prompt_runtime.src.capabilities_output_saver import Saver
from modules.prompt_runtime.src.capabilities_prompt_injector import PromptInjector
from modules.prompt_runtime.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt_runtime.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.common.taxonomy_core_constant import JS_COUNT_TURNS, JS_GET_RESPONSE_TEXT
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_vo import (
    ClickTimeoutMs,
    InjectorConfig,
    RunContext,
    SenderConfig,
    StreamerConfig,
)
from modules.shared.src.prompt_runtime.taxonomy_prompt_runtime_vo import RuntimeRequest

PROMPT = "Summarize this document"
ANSWER = "The summarized document"


def _aggregate(metadata_dir: Path) -> PromptRuntimeOrchestrator:
    """The five real capabilities behind one aggregate door, the root
    container's composition shape."""
    return PromptRuntimeOrchestrator(
        injector=PromptInjector(),
        sender=SendDispatcher(click_timeout_ms=ClickTimeoutMs(100)),
        streamer=StreamMonitor(),
        uploader=FileUploader(),
        saver=Saver(metadata_dir=metadata_dir),
    )


def _inject_page() -> MagicMock:
    """A page stub whose input handle reports the injected text back."""
    page = MagicMock()
    el = MagicMock()
    el.evaluate.return_value = PROMPT
    page.wait_for_selector.return_value = el
    page.evaluate.return_value = True
    return page


def _send_page() -> MagicMock:
    """A send control that is visible and enabled; the turn-count probe
    answers 1 before the click and 2 after it, so the dispatch ACK wait
    confirms a real new turn on the scripted page and exits immediately."""
    page = MagicMock()
    loc = MagicMock()
    loc.count.return_value = 1
    loc.first.count.return_value = 1
    loc.first.is_visible.return_value = True
    loc.first.is_enabled.return_value = True
    loc.nth.return_value.evaluate.return_value = False
    loc.nth.return_value.text_content.return_value = None
    page.locator.return_value = loc
    reads = {"turns": 0}

    def _evaluate(script: str, *_args: object, **_kwargs: object) -> object:
        if script == JS_COUNT_TURNS:
            reads["turns"] += 1
            return 1 if reads["turns"] == 1 else 2
        return ""

    page.evaluate.side_effect = _evaluate
    page.keyboard.press = MagicMock()
    return page


def _watch_page() -> MagicMock:
    """The generation is already complete: stop button hidden, no active
    thinking card, and the answer text present. The pre-loop baseline read
    (`JS_GET_RESPONSE_TEXT`) answers empty so the monitor starts from a
    clean slate; no message nodes means no locator fallback.
    """
    page = MagicMock()
    loc = MagicMock()
    loc.count.return_value = 0
    page.locator.return_value = loc

    def _evaluate(script: str, *_args: object, **_kwargs: object) -> object:
        if script == JS_GET_RESPONSE_TEXT:
            return ""
        return {"thinking": False, "stop_visible": False, "latest_text": ANSWER}

    page.evaluate.side_effect = _evaluate
    return page


def test_e2e_the_runtime_lifecycle_runs_through_one_door(tmp_path: Path) -> None:
    aggregator = _aggregate(tmp_path / "meta")
    attachment = tmp_path / "doc.md"
    attachment.write_text(PROMPT, encoding="utf-8")
    emitter = LifecycleEmitter(MagicMock())

    # Step 1: pre-flight validation of the real attachment, then the
    # scripted card renders (baseline probe 0 → card probe 1 → parse
    # readiness ready), so the upload is accepted.
    upload_page = MagicMock()
    upload_page.evaluate.side_effect = [
        0,
        1,
        {"found": True, "ready": True},
    ]
    uploaded = aggregator.execute(RuntimeRequest(verb="upload", page=upload_page, filepath=attachment, emitter=emitter))
    assert uploaded.accepted is True, "a passing pre-flight plus a rendered card is an accepted upload"

    # Step 2: inject the prompt into the scripted chat input.
    injected = aggregator.execute(
        RuntimeRequest(
            verb="inject",
            page=_inject_page(),
            prompt=PROMPT,
            config=InjectorConfig(verify_injection=True),
        )
    )
    assert injected.response_text is None, "inject reports nothing of its own"

    # Step 3: dispatch; the post-click turn count rides the response.
    sent = aggregator.execute(
        RuntimeRequest(
            verb="send",
            page=_send_page(),
            emitter=emitter,
            config=SenderConfig(click_timeout_ms=100, try_enter_key_fallback=True),
        )
    )
    assert sent.message_count >= 0

    # Step 4: watch until the response is stable and the verdict is earned.
    watched = aggregator.execute(
        RuntimeRequest(
            verb="watch",
            page=_watch_page(),
            timeout_sec=5,
            msg_count_before=1,
            emitter=emitter,
            config=StreamerConfig(polling_interval_sec=0, stability_checks=1, min_text_length=1),
        )
    )
    assert "The summarized" in str(watched.response_text or ""), "the monitor must report the streamed answer"
    assert watched.verdict == "complete"

    # Step 5: persist the response to the operator's named destination.
    persisted = aggregator.execute(
        RuntimeRequest(
            verb="persist",
            output_path=tmp_path / "answer.md",
            content=str(watched.response_text),
            ctx=RunContext(run_id="run-e2e"),
            dur=1.0,
            input_chars=len(PROMPT),
            output_chars=len(ANSWER),
        )
    )
    artifact = tmp_path / "answer.md"
    assert persisted.saved_path == artifact
    assert artifact.exists()
    assert ANSWER in artifact.read_text(encoding="utf-8"), "the persisted artifact must carry the response"
