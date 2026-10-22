"""Unit tests for JobStorage capability and AgentJobOrchestrator."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.jobs.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.shared.src.common.taxonomy_core_constant import JOB_HEARTBEAT_LEASE_SEC
from modules.shared.src.common.taxonomy_core_entity import CircuitBreaker
from modules.shared.src.common.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
)
from modules.shared.src.common.taxonomy_core_vo import (
    FailureThreshold,
    JobId,
    JobRecord,
    ResponseText,
    WindowSec,
)
from modules.shared.src.jobs.taxonomy_jobs_vo import JobRequest
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptResponse


def _submit_file(
    orchestrator: AgentJobOrchestrator,
    prompt_file: Path,
    output_file: Path | None = None,
) -> JobRecord:
    """Submit a prompt-file job through the aggregate and return its record."""
    record = orchestrator.execute(
        JobRequest(verb="submit_file_job", prompt_file=prompt_file, output_file=output_file)
    ).record
    assert record is not None
    return record


def _job_status(orchestrator: AgentJobOrchestrator, job_id: str) -> JobRecord | None:
    """Read a job back through the aggregate."""
    return orchestrator.execute(JobRequest(verb="get_job_status", job_id=JobId(job_id))).record


class TestJobStorage(unittest.TestCase):
    """Test suite for JobStorage persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.temp_dir.name)
        self.mgr = JobStorage(storage_dir=self.storage_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_and_get_job(self) -> None:
        rec = JobRecord(
            job_id="test_job_1",
            latest_event=EVENT_DISPATCH_ACKNOWLEDGED.value,
            completed=False,
            created_at="2026-08-27T00:00:00Z",
            input_file="/tmp/prompt.md",
        )
        self.mgr.save_job(rec)

        loaded = self.mgr.get_job(JobId("test_job_1"))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.job_id, "test_job_1")
        self.assertEqual(loaded.latest_event, EVENT_DISPATCH_ACKNOWLEDGED.value)
        self.assertFalse(loaded.completed)
        self.assertEqual(loaded.input_file, "/tmp/prompt.md")

    def test_reconcile_zombies_marks_dead_owner_pid_as_failed(self) -> None:
        rec = JobRecord(
            job_id="zombie_job_1",
            latest_event=EVENT_DISPATCH_ACKNOWLEDGED.value,
            completed=False,
            created_at="2026-08-27T00:00:00Z",
            owner_pid=999999999,  # non-existent process PID
        )
        self.mgr.save_job(rec)

        reconciled = self.mgr.reconcile_zombies()
        self.assertEqual(reconciled, 1)

        loaded = self.mgr.get_job(JobId("zombie_job_1"))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertTrue(loaded.completed)
        self.assertEqual(loaded.error, "process exited before completion")


class TestAgentJobOrchestrator(unittest.TestCase):
    """Test suite for AgentJobOrchestrator."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = JobStorage(storage_dir=Path(self.temp_dir.name))
        self.mock_file_only = MagicMock()
        self.mock_attachment = MagicMock()
        self.orchestrator = AgentJobOrchestrator(
            storage=self.storage,
            file_only=self.mock_file_only,
            attachment=self.mock_attachment,
            max_workers=1,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_submit_file_job(self) -> None:
        self.mock_file_only.execute.return_value = PromptResponse(response_text=ResponseText("Test response output"))

        prompt_file = Path(self.temp_dir.name) / "prompt.md"
        prompt_file.write_text("Hello", encoding="utf-8")

        rec = _submit_file(self.orchestrator, prompt_file)
        self.assertEqual(rec.latest_event, EVENT_DISPATCH_ACKNOWLEDGED.value)
        self.assertFalse(rec.completed)
        self.assertTrue(rec.job_id.startswith("file_"))

        # Wait for thread execution
        self.orchestrator._executor.shutdown(wait=True)

        final_rec = _job_status(self.orchestrator, rec.job_id)
        self.assertIsNotNone(final_rec)
        assert final_rec is not None
        self.assertEqual(final_rec.latest_event, EVENT_GENERATION_FINISHED.value)
        self.assertTrue(final_rec.completed)
        self.assertIn("Test response", final_rec.result_preview or "")

    def test_submit_record_carries_owner_pid(self) -> None:
        """Issue #376: submit must set ``owner_pid`` so zombies are identifiable."""
        self.mock_file_only.execute.return_value = PromptResponse(response_text=ResponseText("Test"))

        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")

        rec = _submit_file(self.orchestrator, prompt_file)
        self.assertEqual(rec.owner_pid, os.getpid())
        self.orchestrator._executor.shutdown(wait=True)


class TestJobOwnershipPreserved(unittest.TestCase):
    """Issue #376: ``owner_pid`` and ``heartbeat_at`` must survive every save
    transition so zombie reconciliation can claim orphaned records."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = JobStorage(storage_dir=Path(self.temp_dir.name))
        self.mock_file_only = MagicMock()
        self.mock_attachment = MagicMock()
        self.orchestrator = AgentJobOrchestrator(
            storage=self.storage,
            file_only=self.mock_file_only,
            attachment=self.mock_attachment,
            max_workers=1,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_owner_pid_and_heartbeat_at_survive_save_started(self) -> None:
        """``_save_started`` must preserve the submitted record's ownership."""
        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")
        self.mock_file_only.execute.return_value = PromptResponse(response_text=ResponseText("ok"))

        rec = _submit_file(self.orchestrator, prompt_file)
        pid = rec.owner_pid
        self.assertIsNotNone(pid)

        # The worker thread is already running; let it save a terminal state.
        self.orchestrator._executor.shutdown(wait=True)

        saved = _job_status(self.orchestrator, rec.job_id)
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.owner_pid, pid)

    def test_submit_is_non_blocking_even_when_rate_limiter_would_starve(self) -> None:
        """Issue #362/#383: ``submit_file_job`` must return within bounded time.

        Throughput is enforced on the worker thread, so a saturated limiter does
        not stall the MCP caller. The submit path raises ``CircuitBreakerOpenError``
        immediately (not ``RateLimitError``) when the submit-time guard rejects,
        returning the reserved slot so the caller can retry.
        """
        from modules.shared.src.common.taxonomy_core_error import CircuitBreakerOpenError

        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")
        self.mock_file_only.execute.return_value = PromptResponse(response_text=ResponseText("ok"))

        # Open the breaker up front — the submit-time guard must refuse immediately.
        throttled = AgentJobOrchestrator(
            storage=self.storage,
            file_only=self.mock_file_only,
            attachment=self.mock_attachment,
            max_workers=1,
            circuit_breaker=CircuitBreaker(threshold=FailureThreshold(1), window_sec=WindowSec(60)),
        )
        throttled._circuit_breaker.record_failure()

        start = time.perf_counter()
        with pytest.raises(CircuitBreakerOpenError):
            _submit_file(throttled, prompt_file)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.5, f"submit took {elapsed:.2f}s — must be sub-500ms when rejected")
        throttled._executor.shutdown(wait=True)


class TestSubmitHeartbeatStamp(unittest.TestCase):
    """Submit must stamp heartbeat_at so a second process cannot zombie a live job."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.temp_dir.name)
        self.storage = JobStorage(storage_dir=self.storage_dir)
        self.mock_file_only = MagicMock()
        self.mock_attachment = MagicMock()
        # Block the worker so the submit→start window stays open.
        self._release = __import__("threading").Event()
        self.mock_file_only.execute.side_effect = lambda *_a, **_k: (
            self._release.wait(timeout=30),
            PromptResponse(response_text=ResponseText("ok")),
        )[1]
        self.orchestrator = AgentJobOrchestrator(
            storage=self.storage,
            file_only=self.mock_file_only,
            attachment=self.mock_attachment,
            max_workers=1,
        )

    def tearDown(self) -> None:
        self._release.set()
        self.orchestrator._executor.shutdown(wait=True)
        self.temp_dir.cleanup()

    def test_submit_record_carries_heartbeat_at(self) -> None:
        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")
        rec = _submit_file(self.orchestrator, prompt_file)
        self.assertIsNotNone(rec.heartbeat_at)

    def test_missing_heartbeat_is_not_stale_within_grace(self) -> None:
        from datetime import UTC, datetime

        fresh = datetime.now(UTC).isoformat()
        self.assertFalse(JobStorage._heartbeat_is_stale(None, fresh))

    def test_missing_heartbeat_is_stale_after_lease(self) -> None:
        from datetime import UTC, datetime, timedelta

        old = (datetime.now(UTC) - timedelta(seconds=JOB_HEARTBEAT_LEASE_SEC * 2)).isoformat()
        self.assertTrue(JobStorage._heartbeat_is_stale(None, old))

    def test_naive_created_at_is_treated_as_utc_not_typeerror(self) -> None:
        # Legacy/corrupt records store offset-naive stamps; must not crash reconcile.
        from datetime import UTC, datetime, timedelta

        fresh = datetime.now(UTC).replace(tzinfo=None).isoformat()
        old = (datetime.now(UTC) - timedelta(seconds=JOB_HEARTBEAT_LEASE_SEC * 2)).replace(tzinfo=None).isoformat()
        self.assertFalse(JobStorage._heartbeat_is_stale(None, fresh))
        self.assertTrue(JobStorage._heartbeat_is_stale(None, old))
        self.assertTrue(JobStorage._heartbeat_is_stale(old, None))
        self.assertFalse(JobStorage._heartbeat_is_stale(fresh, None))

    def test_non_string_stamp_is_treated_as_stale_not_attributeerror(self) -> None:
        # Corrupt JSON can store a numeric stamp; must not crash construction-time reconcile.
        self.assertTrue(JobStorage._heartbeat_is_stale(None, 12345))
        self.assertTrue(JobStorage._heartbeat_is_stale(None, 12.5))
        self.assertTrue(JobStorage._heartbeat_is_stale(12345, None))
        self.assertTrue(JobStorage._heartbeat_is_stale(12.5, None))

    def test_live_job_is_not_zombied_by_second_storage_construct(self) -> None:
        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")
        rec = _submit_file(self.orchestrator, prompt_file)
        # Second process in the submit→start window must not mark it failed.
        again = JobStorage(storage_dir=self.storage_dir)
        loaded = again.get_job(rec.job_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertFalse(loaded.completed, "live submit window job was marked zombie")


class TestTerminalSaveAfterHeartbeatJoin(unittest.TestCase):
    """Terminal state must survive the heartbeat (join-before-save)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = JobStorage(storage_dir=Path(self.temp_dir.name))
        self.mock_file_only = MagicMock()
        self.mock_attachment = MagicMock()
        self.orchestrator = AgentJobOrchestrator(
            storage=self.storage,
            file_only=self.mock_file_only,
            attachment=self.mock_attachment,
            max_workers=1,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_completed_record_is_not_demoted_by_a_late_beat(self) -> None:
        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")
        self.mock_file_only.execute.return_value = PromptResponse(response_text=ResponseText("ok"))
        rec = _submit_file(self.orchestrator, prompt_file)
        self.orchestrator._executor.shutdown(wait=True)
        loaded = _job_status(self.orchestrator, rec.job_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertTrue(loaded.completed)
        self.assertIsNotNone(loaded.completed_at)
        self.assertIsNotNone(loaded.result_preview)
        # A beat after completion must refuse to rewrite the record.
        before = loaded.completed_at
        self.orchestrator._refresh_heartbeat(JobId(rec.job_id))
        after = _job_status(self.orchestrator, rec.job_id)
        assert after is not None
        self.assertTrue(after.completed)
        self.assertEqual(after.completed_at, before)
        self.assertEqual(after.result_preview, loaded.result_preview)


if __name__ == "__main__":
    unittest.main()
