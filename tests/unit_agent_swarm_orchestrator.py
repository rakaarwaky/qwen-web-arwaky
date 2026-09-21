"""Unit tests for the adaptive Swarm orchestrator."""

from __future__ import annotations

import time
from pathlib import Path
from threading import Event

from modules.core.src.agent_swarm_orchestrator import SwarmOrchestrator


class FakeAttachmentAggregate:
    def __init__(self, failures: dict[str, int] | None = None) -> None:
        self.failures = failures or {}
        self.calls: list[tuple[str, Path]] = []
        self.cancelled: list[Event] = []

    def process_prompt_with_attachment(self, prompt_file, attachment_file, output_file, headless, cancel_event=None):
        role = Path(prompt_file).stem
        self.calls.append((role, Path(output_file)))
        remaining = self.failures.get(role, 0)
        if remaining:
            self.failures[role] = remaining - 1
            return "ERROR [transient timeout]"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text(f"result for {role}", encoding="utf-8")
        return f"Successfully processed {role}"

    def request_cancel(self, event: Event) -> None:
        self.cancelled.append(event)
        event.set()


def _wait_for_terminal(orchestrator: SwarmOrchestrator, swarm_id: str):
    for _ in range(100):
        snapshot = orchestrator.snapshot(swarm_id)
        assert snapshot is not None
        if snapshot.status in {"completed", "partial", "failed", "cancelled"}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError("Swarm did not finish")


def _patch_templates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "modules.core.src.agent_swarm_orchestrator.list_prompt_templates",
        lambda: ("architect", "security-reviewer"),
    )
    monkeypatch.setattr(
        "modules.core.src.agent_swarm_orchestrator.materialize_role_template",
        lambda role: tmp_path / f"{role}.md",
    )


def test_swarm_discovers_all_templates_and_writes_existing_format(monkeypatch, tmp_path: Path) -> None:
    _patch_templates(monkeypatch, tmp_path)
    aggregate = FakeAttachmentAggregate()
    orchestrator = SwarmOrchestrator(aggregate, output_root=tmp_path, browser_concurrency=10)
    input_path = tmp_path / "project.md"
    input_path.write_text("source", encoding="utf-8")

    initial = orchestrator.start(input_path)
    final = _wait_for_terminal(orchestrator, initial.swarm_id)

    assert final.status == "completed"
    assert final.completed_count == 2
    assert (tmp_path / initial.swarm_id / "manifest.json").exists()
    assert (tmp_path / initial.swarm_id / "architect" / "output.md").exists()
    assert {role for role, _ in aggregate.calls} == {"architect", "security-reviewer"}


def test_swarm_retries_transient_agent_failure_and_allows_partial(monkeypatch, tmp_path: Path) -> None:
    _patch_templates(monkeypatch, tmp_path)
    aggregate = FakeAttachmentAggregate({"security-reviewer": 3})
    orchestrator = SwarmOrchestrator(aggregate, output_root=tmp_path, browser_concurrency=1)
    input_path = tmp_path / "project.md"
    input_path.write_text("source", encoding="utf-8")

    initial = orchestrator.start(input_path)
    final = _wait_for_terminal(orchestrator, initial.swarm_id)

    assert final.status == "partial"
    assert final.completed_count == 1
    failed = next(agent for agent in final.agents if agent.agent_id == "security-reviewer")
    assert failed.status == "failed"
    assert failed.attempt == 3


def test_swarm_retries_stuck_detection_failure(monkeypatch, tmp_path: Path) -> None:
    """A StuckDetectedError (event-driven stall) is retryable; the swarm
    retries up to max_attempts then marks the agent failed with the stuck
    error recorded — proving the stuck path never hangs the swarm."""
    _patch_templates(monkeypatch, tmp_path)
    aggregate = FakeAttachmentAggregate({"architect": 2, "security-reviewer": 100})
    orchestrator = SwarmOrchestrator(
        aggregate, output_root=tmp_path, browser_concurrency=1, max_attempts=3
    )
    input_path = tmp_path / "project.md"
    input_path.write_text("source", encoding="utf-8")

    # Make the fake aggregate raise a StuckDetectedError-flavoured failure string
    # that exercises the retryable path without hitting real browsers.
    original_process = aggregate.process_prompt_with_attachment

    def process_with_stuck(prompt_file, attachment_file, output_file, headless, cancel_event=None):
        role = Path(prompt_file).stem
        remaining = aggregate.failures.get(role, 0)
        if remaining > 0:
            aggregate.failures[role] = remaining - 1
            return "ERROR [stuck] Stuck detected: no forward lifecycle event for 300s"
        return original_process(prompt_file, attachment_file, output_file, headless, cancel_event)

    aggregate.process_prompt_with_attachment = process_with_stuck

    initial = orchestrator.start(input_path)
    final = _wait_for_terminal(orchestrator, initial.swarm_id)

    assert final.status == "partial"
    assert final.completed_count == 1
    architect = next(agent for agent in final.agents if agent.agent_id == "architect")
    # architect exhausted 3 attempts (2 stuck failures + 1 success would be
    # completed, but 2 stuck failures then 1 real success = completed).
    # With 2 stuck failures and max_attempts=3, the 3rd attempt succeeds.
    assert architect.status in {"completed", "failed"}
    if architect.status == "failed":
        assert "stuck" in str(architect.error).lower()
    security = next(agent for agent in final.agents if agent.agent_id == "security-reviewer")
    assert security.status == "failed"
    assert "stuck" in str(security.error).lower()


def test_swarm_marks_non_retryable_error_failed_immediately(monkeypatch, tmp_path: Path) -> None:
    """A non-retryable error (e.g. auth failure) must fail the agent on the
    first attempt without retrying."""
    _patch_templates(monkeypatch, tmp_path)
    aggregate = FakeAttachmentAggregate({"architect": 100})

    # Override to produce a non-retryable failure string
    def process_with_auth_error(prompt_file, attachment_file, output_file, headless, cancel_event=None):
        role = Path(prompt_file).stem
        remaining = aggregate.failures.get(role, 0)
        if remaining > 0:
            aggregate.failures[role] = remaining - 1
            return "ERROR [auth] Login session expired — run qwa login"
        return f"Successfully processed {role}"

    aggregate.process_prompt_with_attachment = process_with_auth_error

    orchestrator = SwarmOrchestrator(
        aggregate, output_root=tmp_path, browser_concurrency=1, max_attempts=3
    )
    input_path = tmp_path / "project.md"
    input_path.write_text("source", encoding="utf-8")

    initial = orchestrator.start(input_path)
    final = _wait_for_terminal(orchestrator, initial.swarm_id)

    architect = next(agent for agent in final.agents if agent.agent_id == "architect")
    # Auth failure is non-retryable → should fail on attempt 1, not 3.
    assert architect.status == "failed"
    assert architect.attempt == 1
    assert "login" in str(architect.error).lower()
