"""Integration tests for the prompt runtime orchestrator with the real capabilities.

These exercise the DI wiring exactly the root container builds it: the
five real ``modules/prompt_runtime`` capabilities composed into
``PromptRuntimeOrchestrator``, then routed through ``execute`` verb by
verb, so a signature or wiring change fails here. Page-dependent verbs use
mock pages the way the unit suite does; the capability and agent under
test are real.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.prompt_runtime.src.agent_prompt_runtime_orchestrator import PromptRuntimeOrchestrator
from modules.prompt_runtime.src.capabilities_file_uploader import FileUploader
from modules.prompt_runtime.src.capabilities_output_saver import Saver
from modules.prompt_runtime.src.capabilities_prompt_injector import PromptInjector
from modules.prompt_runtime.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt_runtime.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.common.taxonomy_core_constant import JS_GET_RESPONSE_TEXT
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.common.taxonomy_core_vo import RunContext, StreamerConfig
from modules.shared.src.common.utility_io_writer import sidecar_path_for
from modules.shared.src.prompt_runtime.contract_prompt_runtime_aggregate import IPromptRuntimeAggregate
from modules.shared.src.prompt_runtime.taxonomy_prompt_runtime_vo import RuntimeRequest, RuntimeResponse


def _orchestrator(metadata_dir: Path) -> PromptRuntimeOrchestrator:
    """Build the aggregate the way the root container composes it."""
    return PromptRuntimeOrchestrator(
        injector=PromptInjector(),
        sender=SendDispatcher(),
        streamer=StreamMonitor(),
        uploader=FileUploader(),
        saver=Saver(metadata_dir=metadata_dir),
    )


def test_integration_orchestrator_boots_with_the_five_real_capabilities(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path / "meta")
    assert isinstance(orchestrator, IPromptRuntimeAggregate)
    assert callable(orchestrator.execute)


def test_integration_persist_verb_writes_a_real_file(tmp_path: Path) -> None:
    """``persist`` routes to the real Saver, so the artifact and sidecar
    land on disk at the named destination."""
    orchestrator = _orchestrator(tmp_path / "meta")
    target = tmp_path / "response.md"

    response = orchestrator.execute(
        RuntimeRequest(
            verb="persist",
            output_path=target,
            content="The saved answer",
            ctx=RunContext(run_id="run-it-1"),
            dur=0.5,
            input_chars=12,
            output_chars=16,
        )
    )

    assert isinstance(response, RuntimeResponse)
    assert target.exists()
    assert "The saved answer" in target.read_text(encoding="utf-8")
    sidecar = sidecar_path_for(target, tmp_path / "meta")
    assert sidecar.exists(), "a persisted response must carry its run sidecar"


def test_integration_upload_verb_rejects_an_oversized_file_pre_flight(tmp_path: Path) -> None:
    """``upload`` routes to the real FileUploader, whose pre-flight
    validation rejects a file over the 100 MiB ceiling before the
    browser ever sees it."""
    orchestrator = _orchestrator(tmp_path / "meta")
    oversized = tmp_path / "big.md"
    oversized.write_bytes(b"0" * (100 * 1024 * 1024 + 1))
    page = MagicMock()

    response = orchestrator.execute(RuntimeRequest(verb="upload", page=page, filepath=oversized))

    assert response.accepted is False, "an oversized attachment must be rejected, not uploaded"


def test_integration_unknown_verb_raises_cli_error(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path / "meta")
    with pytest.raises(QwenCliError, match="No prompt-runtime capability"):
        orchestrator.execute(RuntimeRequest(verb="process_direct_prompt"))


def test_integration_watch_verb_needs_an_emitter(tmp_path: Path) -> None:
    """A ``watch`` without the lifecycle emitter is refused: the monitor
    writes every state change through it."""
    orchestrator = _orchestrator(tmp_path / "meta")
    page = MagicMock()
    with pytest.raises(QwenCliError, match="emitter"):
        orchestrator.execute(RuntimeRequest(verb="watch", page=page))


def test_integration_send_verb_needs_an_emitter(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path / "meta")
    page = MagicMock()
    with pytest.raises(QwenCliError, match="emitter"):
        orchestrator.execute(RuntimeRequest(verb="send", page=page))


def test_integration_persist_verb_needs_a_destination(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path / "meta")
    with pytest.raises(QwenCliError, match="output_path"):
        orchestrator.execute(RuntimeRequest(verb="persist", content="orphan text"))


def test_integration_upload_verb_needs_a_file(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path / "meta")
    page = MagicMock()
    with pytest.raises(QwenCliError, match="filepath"):
        orchestrator.execute(RuntimeRequest(verb="upload", page=page))


def test_integration_emit_a_verdict_from_a_completed_stream(tmp_path: Path) -> None:
    """The page probe settles on terminal values, so the real monitor's
    wait loop ends instead of exhausting a side-effect list. The pre-loop
    baseline read answers empty; no message nodes means no fallback."""
    orchestrator = _orchestrator(tmp_path / "meta")
    page = MagicMock()
    loc = MagicMock()
    loc.count.return_value = 0
    page.locator.return_value = loc

    def _evaluate(script: str, *_args: object, **_kwargs: object) -> object:
        if script == JS_GET_RESPONSE_TEXT:
            return ""
        return {"thinking": False, "stop_visible": False, "latest_text": "Done"}

    page.evaluate.side_effect = _evaluate
    emitter = LifecycleEmitter(MagicMock())

    response = orchestrator.execute(
        RuntimeRequest(
            verb="watch",
            page=page,
            timeout_sec=5,
            msg_count_before=1,
            emitter=emitter,
            config=StreamerConfig(polling_interval_sec=0, stability_checks=1, min_text_length=1),
        )
    )

    assert response.response_text is not None
    assert "Done" in str(response.response_text)
    assert response.verdict == "complete"
