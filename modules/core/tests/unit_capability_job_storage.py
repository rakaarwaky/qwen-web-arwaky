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
from modules.shared.src.taxonomy_core_entity import CircuitBreaker
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
)
from modules.shared.src.taxonomy_core_vo import (
    FailureThreshold,
    HeadlessFlag,
    JobId,
    JobRecord,
    ResponseText,
    WindowSec,
)


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

    def test_list_jobs(self) -> None:
        for i in range(3):
            self.mgr.save_job(
                JobRecord(
                    job_id=f"job_{i}",
                    latest_event=EVENT_GENERATION_FINISHED.value,
                    completed=True,
                    created_at=f"2026-08-27T0{i}:00:00Z",
                )
            )
        jobs = self.mgr.list_jobs(limit=10)
        self.assertEqual(len(jobs), 3)

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
        self.mock_file_only.process_prompt_file_only.return_value = ResponseText("Test response output")

        prompt_file = Path(self.temp_dir.name) / "prompt.md"
        prompt_file.write_text("Hello", encoding="utf-8")

        rec = self.orchestrator.submit_file_job(
            prompt_file=prompt_file,
            headless=HeadlessFlag(True),
        )
        self.assertEqual(rec.latest_event, EVENT_DISPATCH_ACKNOWLEDGED.value)
        self.assertFalse(rec.completed)
        self.assertTrue(rec.job_id.startswith("file_"))

        # Wait for thread execution
        self.orchestrator._executor.shutdown(wait=True)

        final_rec = self.orchestrator.get_job_status(JobId(rec.job_id))
        self.assertIsNotNone(final_rec)
        assert final_rec is not None
        self.assertEqual(final_rec.latest_event, EVENT_GENERATION_FINISHED.value)
        self.assertTrue(final_rec.completed)
        self.assertIn("Test response", final_rec.result_preview or "")

    def test_submit_record_carries_owner_pid(self) -> None:
        """Issue #376: submit must set ``owner_pid`` so zombies are identifiable."""
        self.mock_file_only.process_prompt_file_only.return_value = ResponseText("Test")

        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")

        rec = self.orchestrator.submit_file_job(prompt_file=prompt_file)
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
        self.mock_file_only.process_prompt_file_only.return_value = ResponseText("ok")

        rec = self.orchestrator.submit_file_job(prompt_file=prompt_file)
        pid = rec.owner_pid
        self.assertIsNotNone(pid)

        # The worker thread is already running; let it save a terminal state.
        self.orchestrator._executor.shutdown(wait=True)

        saved = self.orchestrator.get_job_status(JobId(rec.job_id))
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved.owner_pid, pid)

    def test_job_status_preserves_owner_pid_through_terminal(self) -> None:
        """A completed job keeps its ``owner_pid`` so zombie reconciliation
        correctly skips it (alive owner = not a zombie)."""
        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")
        self.mock_file_only.process_prompt_file_only.return_value = ResponseText("ok")

        rec = self.orchestrator.submit_file_job(prompt_file=prompt_file)
        pid = rec.owner_pid

        self.orchestrator._executor.shutdown(wait=True)

        loaded = self.orchestrator.get_job_status(JobId(rec.job_id))
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertTrue(loaded.completed)
        self.assertEqual(loaded.owner_pid, pid)

    def test_submit_is_non_blocking_even_when_rate_limiter_would_starve(self) -> None:
        """Issue #362/#383: ``submit_file_job`` must return within bounded time.

        Throughput is enforced on the worker thread, so a saturated limiter does
        not stall the MCP caller. The submit path raises ``CircuitBreakerOpenError``
        immediately (not ``RateLimitError``) when the submit-time guard rejects,
        returning the reserved slot so the caller can retry.
        """
        from modules.shared.src.taxonomy_core_error import CircuitBreakerOpenError

        prompt_file = Path(self.temp_dir.name) / "p.md"
        prompt_file.write_text("hi", encoding="utf-8")
        self.mock_file_only.process_prompt_file_only.return_value = ResponseText("ok")

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
            throttled.submit_file_job(prompt_file=prompt_file)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.5, f"submit took {elapsed:.2f}s — must be sub-500ms when rejected")
        throttled._executor.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
