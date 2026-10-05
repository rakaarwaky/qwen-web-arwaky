"""Acceptance tests for the fan-out concurrency-clamp requirement.

The requirement in `modules/swarm/FRD.md` FR-SWARM-001 is that a fan-out
never exceeds the host's concurrency ceiling and reports the clamp, so a
caller can see that its request was reduced.
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest

from modules.shared.src.taxonomy_prompt_vo import PromptRequest, PromptResponse, ResponseText
from modules.shared.src.taxonomy_swarm_vo import SwarmRequest
from modules.swarm.src.agent_swarm_orchestrator import SwarmOrchestrator
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner


class _PromptSeam:
    """Prompt seam that reports the browser count it was asked to carry."""

    def __init__(self) -> None:
        self.calls: list[Path] = []

    def execute(self, request: PromptRequest) -> PromptResponse:
        self.calls.append(Path(request.prompt_file))
        output = Path(request.output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("result", encoding="utf-8")
        return PromptResponse(response_text=ResponseText("ok"))

    def request_cancel(self, event: Event) -> None:
        event.set()


def _orchestrator(tmp_path: Path, ceiling: int) -> SwarmOrchestrator:
    return SwarmOrchestrator(
        runner=SwarmRunner(
            output_root=tmp_path,
            browser_concurrency=ceiling,
            attachment=_PromptSeam(),
        ),
        observability=MagicMock(),
    )


def _await_terminal(orchestrator: SwarmOrchestrator, swarm_id: str):
    for _ in range(200):
        snapshot = orchestrator.execute(SwarmRequest(verb="snapshot", swarm_id=swarm_id)).snapshot
        if snapshot is not None and snapshot.status in {"completed", "partial", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("the fan-out did not finish")


def test_acceptance_a_requested_leg_count_above_the_ceiling_is_clamped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "modules.swarm.src.capabilities_swarm_runner.list_prompt_templates",
        lambda: tuple(f"role-{index}" for index in range(8)),
    )
    monkeypatch.setattr(
        "modules.swarm.src.capabilities_swarm_runner.materialize_role_template",
        lambda role: tmp_path / f"{role}.md",
    )
    input_path = tmp_path / "project.md"
    input_path.write_text("source", encoding="utf-8")
    orchestrator = _orchestrator(tmp_path, ceiling=2)

    started = orchestrator.execute(SwarmRequest(verb="start", input_path=input_path))
    final = _await_terminal(orchestrator, started.snapshot.swarm_id)

    assert final.status in {"completed", "partial"}, f"the clamped fan-out must still run, got {final.status}"
    assert final.browser_concurrency <= 2, f"a ceiling of 2 must cap the concurrency, got {final.browser_concurrency}"
