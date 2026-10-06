"""End-to-end tests for the job aggregate over the full verb cycle.

These drive ``AgentJobOrchestrator`` with real storage, the real executor,
and prompt seams that only write their result files, so the
submit-then-poll-then-reclaim cycle a caller runs is exercised end to end
without a browser or a network.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.jobs.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.shared.src.taxonomy_core_error import JobQueueFullError
from modules.shared.src.taxonomy_core_vo import JobId, JobLimit, JobRecord
from modules.shared.src.taxonomy_jobs_vo import JobRequest
from modules.shared.src.taxonomy_prompt_vo import PromptRequest, PromptResponse, ResponseText


def _writing_seam() -> MagicMock:
    """Return a prompt seam that writes the named response file."""

    def _execute(request: PromptRequest) -> PromptResponse:
        output = Path(str(request.output_file)) if request.output_file else Path("/dev/null")
        if output != Path("/dev/null"):
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
    """Poll the status verb until the record reaches a terminal state."""
    for _ in range(300):
        record = orchestrator.execute(JobRequest(verb="get_job_status", job_id=job_id)).record
        if record is not None and record.completed:
            return record
        time.sleep(0.01)
    raise AssertionError("the job did not reach a terminal state")


def test_e2e_submit_poll_and_list_a_file_job(tmp_path: Path) -> None:
    """The full request-to-result path: submit, poll, list, confirm state."""
    orchestrator = _orchestrator(tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    output = tmp_path / "out.md"

    submitted = orchestrator.execute(JobRequest(verb="submit_file_job", prompt_file=prompt, output_file=output)).record
    assert submitted is not None
    assert submitted.job_id

    finished = _await_terminal(orchestrator, submitted.job_id)
    assert finished.completed
    assert finished.error is None, "a successful seam must not fail the job"
    assert Path(finished.output_file).read_text(encoding="utf-8") == "answer"

    listed = orchestrator.execute(JobRequest(verb="list_jobs", limit=JobLimit(10))).records
    assert listed is not None
    assert any(r.job_id == submitted.job_id for r in listed)
    assert all(r.completed for r in listed)


def test_e2e_unknown_status_reported_not_raised(tmp_path: Path) -> None:
    """A status read for an id the storage does not know returns cleanly."""
    orchestrator = _orchestrator(tmp_path)

    response = orchestrator.execute(JobRequest(verb="get_job_status", job_id=JobId("no-such-job")))
    assert response.record is None


def test_e2e_submission_refused_at_admission_leaves_no_record(tmp_path: Path) -> None:
    """A rejected submission is not persisted: the queue cap is the guard."""
    orchestrator = AgentJobOrchestrator(
        storage=JobStorage(storage_dir=tmp_path / "jobs"),
        file_only=_writing_seam(),
        attachment=_writing_seam(),
        max_workers=1,
        max_pending_jobs=1,
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")

    first = orchestrator.execute(
        JobRequest(verb="submit_file_job", prompt_file=prompt, output_file=tmp_path / "out.md")
    ).record
    assert first is not None

    with pytest.raises(JobQueueFullError):
        orchestrator.execute(JobRequest(verb="submit_file_job", prompt_file=prompt, output_file=tmp_path / "out2.md"))

    # The rejected submission never reached storage.
    listed = orchestrator.execute(JobRequest(verb="list_jobs", limit=JobLimit(10))).records
    assert listed is not None
    assert len([r for r in listed if r.job_id != first.job_id]) == 0
