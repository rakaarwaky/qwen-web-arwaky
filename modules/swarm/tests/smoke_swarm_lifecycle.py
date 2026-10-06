"""Smoke tests for the swarm runner's concurrency ceiling and discovery.

The smoke path is "start, poll, cancel" without any real work: these check
that the runner answers the read-only verbs and reports a discovery set
before a fan-out has begun.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from modules.shared.src.taxonomy_prompt_vo import PromptResponse, ResponseText
from modules.shared.src.taxonomy_swarm_vo import SwarmRequest
from modules.swarm.src.agent_swarm_orchestrator import SwarmOrchestrator
from modules.swarm.src.capabilities_swarm_runner import SwarmRunner


def _orchestrator(ceiling: int = 4) -> SwarmOrchestrator:
    return SwarmOrchestrator(
        runner=SwarmRunner(
            output_root=Path("/tmp/qwen-smoke-output"),
            browser_concurrency=ceiling,
            attachment=MagicMock(execute=lambda request: PromptResponse(response_text=ResponseText("ok"))),
        ),
        observability=MagicMock(),
    )


def test_smoke_the_aggregate_reports_its_concurrency_ceiling() -> None:
    assert _orchestrator(ceiling=4).browser_concurrency == 4


def test_smoke_a_snapshot_of_a_handle_that_never_started_reports_nothing() -> None:
    assert _orchestrator().execute(SwarmRequest(verb="snapshot", swarm_id="never-started")).snapshot is None


def test_smoke_a_cancel_of_a_handle_that_never_started_reports_nothing() -> None:
    assert _orchestrator().execute(SwarmRequest(verb="cancel", swarm_id="never-started")).snapshot is None


def test_smoke_a_start_without_an_input_reports_the_reason() -> None:
    response = _orchestrator().execute(SwarmRequest(verb="start"))

    assert response.error, "a start with no input must name the reason it could not run"
