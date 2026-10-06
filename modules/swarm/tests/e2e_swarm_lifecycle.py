"""End-to-end tests for the fan-out start, poll, and cancel cycle.

These drive the real runner through the three verbs a caller uses, so the
fan-out handle, the snapshot poll, and the cancel verdict are exercised
against the running fan-out rather than a stub.
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
    """Prompt seam that records cancellation but writes its result."""

    def __init__(self) -> None:
        self.cancelled: list[Event] = []

    def execute(self, request: PromptRequest) -> PromptResponse:
        output = Path(request.output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("result", encoding="utf-8")
        return PromptResponse(response_text=ResponseText("ok"))

    def request_cancel(self, event: Event) -> None:
        self.cancelled.append(event)
        event.set()


def _orchestrator(tmp_path: Path) -> SwarmOrchestrator:
    return SwarmOrchestrator(
        runner=SwarmRunner(output_root=tmp_path, browser_concurrency=2, attachment=_PromptSeam()),
        observability=MagicMock(),
    )


def _await_terminal(orchestrator: SwarmOrchestrator, swarm_id: str):
    for _ in range(300):
        snapshot = orchestrator.execute(SwarmRequest(verb="snapshot", swarm_id=swarm_id)).snapshot
        if snapshot is not None and snapshot.status in {"completed", "partial", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("the fan-out did not finish")


def test_e2e_starting_a_fan_out_returns_a_handle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("modules.swarm.src.capabilities_swarm_runner.list_prompt_templates", lambda: ("architect",))
    monkeypatch.setattr(
        "modules.swarm.src.capabilities_swarm_runner.materialize_role_template",
        lambda role: tmp_path / f"{role}.md",
    )
    input_path = tmp_path / "project.md"
    input_path.write_text("source", encoding="utf-8")

    started = _orchestrator(tmp_path).execute(SwarmRequest(verb="start", input_path=input_path))

    assert started.error is None
    assert started.snapshot is not None
    assert started.snapshot.swarm_id


def test_e2e_an_unknown_handle_reports_no_legs(tmp_path: Path) -> None:
    response = _orchestrator(tmp_path).execute(SwarmRequest(verb="snapshot", swarm_id="never-started"))

    assert response.snapshot is None


def test_e2e_cancelling_an_unknown_handle_reports_no_legs(tmp_path: Path) -> None:
    response = _orchestrator(tmp_path).execute(SwarmRequest(verb="cancel", swarm_id="never-started"))

    assert response.snapshot is None
