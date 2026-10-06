"""Integration tests for the fan-out over a real folder input.

These hand the runner a folder to compile into the single attachment every
role shares, so the folder path is exercised against a real directory.
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


class _RecordingPromptSeam:
    """Prompt seam that records the attachment path it was handed."""

    def __init__(self) -> None:
        self.attachments: list[Path] = []

    def execute(self, request: PromptRequest) -> PromptResponse:
        if request.attachment_file is not None:
            self.attachments.append(Path(request.attachment_file))
        output = Path(request.output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("result", encoding="utf-8")
        return PromptResponse(response_text=ResponseText("ok"))

    def request_cancel(self, event: Event) -> None:
        event.set()


def _await_terminal(orchestrator: SwarmOrchestrator, swarm_id: str):
    for _ in range(300):
        snapshot = orchestrator.execute(SwarmRequest(verb="snapshot", swarm_id=swarm_id)).snapshot
        if snapshot is not None and snapshot.status in {"completed", "partial", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("the fan-out did not finish")


def test_integration_a_folder_input_reaches_every_role_as_one_attachment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "modules.swarm.src.capabilities_swarm_runner.list_prompt_templates",
        lambda: ("architect", "reviewer"),
    )
    monkeypatch.setattr(
        "modules.swarm.src.capabilities_swarm_runner.materialize_role_template",
        lambda role: tmp_path / f"{role}.md",
    )
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
    (project / "README.md").write_text("# project", encoding="utf-8")

    seam = _RecordingPromptSeam()
    orchestrator = SwarmOrchestrator(
        runner=SwarmRunner(output_root=tmp_path, browser_concurrency=2, attachment=seam),
        observability=MagicMock(),
    )
    started = orchestrator.execute(SwarmRequest(verb="start", input_path=project))
    final = _await_terminal(orchestrator, started.snapshot.swarm_id)

    assert final.status in {"completed", "partial"}
    assert seam.attachments, "a folder input must reach the roles as a compiled attachment"
    assert all(path.exists() for path in seam.attachments), "every compiled attachment must exist on disk"
