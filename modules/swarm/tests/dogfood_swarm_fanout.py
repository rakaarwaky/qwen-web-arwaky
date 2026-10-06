"""Dogfood tests for a full fan-out over the real runner.

These start a real fan-out against a stub prompt seam, so the runner's
scheduling, per-leg output files, and terminal status are exercised
end to end. No browser is launched and no network is touched.
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

_TERMINAL = {"completed", "partial", "failed", "cancelled"}


class _PromptSeam:
    """Prompt seam that writes a response file per leg."""

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


def _await_terminal(orchestrator: SwarmOrchestrator, swarm_id: str):
    for _ in range(300):
        snapshot = orchestrator.execute(SwarmRequest(verb="snapshot", swarm_id=swarm_id)).snapshot
        if snapshot is not None and snapshot.status in _TERMINAL:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("the fan-out did not finish")


def _start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, roles: int) -> tuple[SwarmOrchestrator, str]:
    monkeypatch.setattr(
        "modules.swarm.src.capabilities_swarm_runner.list_prompt_templates",
        lambda: tuple(f"role-{index}" for index in range(roles)),
    )
    monkeypatch.setattr(
        "modules.swarm.src.capabilities_swarm_runner.materialize_role_template",
        lambda role: tmp_path / f"{role}.md",
    )
    input_path = tmp_path / "project.md"
    input_path.write_text("source", encoding="utf-8")
    orchestrator = SwarmOrchestrator(
        runner=SwarmRunner(output_root=tmp_path, browser_concurrency=4, attachment=_PromptSeam()),
        observability=MagicMock(),
    )
    started = orchestrator.execute(SwarmRequest(verb="start", input_path=input_path))
    return orchestrator, started.snapshot.swarm_id


def test_dogfood_a_fan_out_runs_every_discovered_role(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    orchestrator, swarm_id = _start(monkeypatch, tmp_path, roles=3)

    final = _await_terminal(orchestrator, swarm_id)

    assert final.status == "completed"
    assert final.completed_count == 3


def test_dogfood_a_fan_out_writes_one_output_directory_per_role(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    orchestrator, swarm_id = _start(monkeypatch, tmp_path, roles=2)

    final = _await_terminal(orchestrator, swarm_id)

    assert final.root_path.is_dir()
    assert list(final.root_path.iterdir()), "a completed fan-out must leave its per-role output behind"
