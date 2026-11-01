"""Smoke test for the prompt runtime aggregate.

Boots the aggregate over the five real capabilities and routes one
trivial verb — ``persist`` to a temporary directory — end to end, so a
boot or wiring regression fails in well under five seconds.
"""

from __future__ import annotations

from pathlib import Path

from modules.prompt_runtime.src.agent_prompt_runtime_orchestrator import PromptRuntimeOrchestrator
from modules.prompt_runtime.src.capabilities_file_uploader import FileUploader
from modules.prompt_runtime.src.capabilities_output_saver import Saver
from modules.prompt_runtime.src.capabilities_prompt_injector import PromptInjector
from modules.prompt_runtime.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt_runtime.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.common.taxonomy_core_vo import RunContext
from modules.shared.src.prompt_runtime.taxonomy_prompt_runtime_vo import RuntimeRequest


def _aggregate(metadata_dir: Path) -> PromptRuntimeOrchestrator:
    return PromptRuntimeOrchestrator(
        injector=PromptInjector(),
        sender=SendDispatcher(),
        streamer=StreamMonitor(),
        uploader=FileUploader(),
        saver=Saver(metadata_dir=metadata_dir),
    )


def test_smoke_the_aggregate_boots_and_persists_one_artifact(tmp_path: Path) -> None:
    target = tmp_path / "smoke.md"

    response = _aggregate(tmp_path / "meta").execute(
        RuntimeRequest(
            verb="persist",
            output_path=target,
            content="The smoke answer",
            ctx=RunContext(),
            dur=0.1,
            input_chars=10,
            output_chars=16,
        )
    )

    assert target.exists()
    assert "The smoke answer" in target.read_text(encoding="utf-8")
    assert response.saved_path == target
    assert str(response.response_text) == "The smoke answer"
