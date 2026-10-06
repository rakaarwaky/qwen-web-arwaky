"""Dogfood tests for job submission against the real storage and pool.

These run the actual job manager over a temporary storage directory with a
prompt seam that writes a response file, so the submit-then-poll lifecycle is
exercised end to end without a browser or a network.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

from modules.jobs.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.shared.src.taxonomy_core_vo import JobRecord
from modules.shared.src.taxonomy_jobs_vo import JobRequest
from modules.shared.src.taxonomy_prompt_vo import PromptRequest, PromptResponse, ResponseText


def _writing_seam() -> MagicMock:
    """Return a prompt seam that writes the named response file."""

    def _execute(request: PromptRequest) -> PromptResponse:
        output = Path(request.output_file)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("answer", encoding="utf-8")
        return PromptResponse(response_text=ResponseText("done"))

    return MagicMock(execute=_execute)


def _orchestrator(tmp_path: Path) -> AgentJobOrchestrator:
    return AgentJobOrchestrator(
        storage=JobStorage(storage_dir=tmp_path / "jobs"),
        file_only=_writing_seam(),
        attachment=_writing_seam(),
        max_workers=1,
    )


def _await_terminal(orchestrator: AgentJobOrchestrator, job_id: str) -> JobRecord:
    for _ in range(300):
        record = orchestrator.execute(JobRequest(verb="get_job_status", job_id=job_id)).record
        if record is not None and record.completed:
            return record
        time.sleep(0.01)
    raise AssertionError("the job did not reach a terminal state")


def test_dogfood_a_submitted_job_returns_a_record_and_then_completes(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")

    submitted = orchestrator.execute(
        JobRequest(verb="submit_file_job", prompt_file=prompt, output_file=tmp_path / "out.md")
    )
    assert submitted.record is not None

    record = _await_terminal(orchestrator, submitted.record.job_id)
    assert record.error is None
    assert (tmp_path / "out.md").read_text(encoding="utf-8") == "answer"


def test_dogfood_listing_recovers_a_record_the_caller_can_still_see(tmp_path: Path) -> None:
    orchestrator = _orchestrator(tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt", encoding="utf-8")
    submitted = orchestrator.execute(
        JobRequest(verb="submit_file_job", prompt_file=prompt, output_file=tmp_path / "out.md")
    )

    listed = orchestrator.execute(JobRequest(verb="list_jobs", limit=10)).records

    assert listed is not None
    assert submitted.record.job_id in {record.job_id for record in listed}
