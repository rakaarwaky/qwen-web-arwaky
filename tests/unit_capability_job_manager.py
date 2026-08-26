"""Unit tests for JobManager capability and AgentJobOrchestrator."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from modules.core.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.core.src.capabilities_job_manager import JobManager
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
)
from modules.shared.src.taxonomy_core_vo import (
    HeadlessFlag,
    JobId,
    JobRecord,
    ResponseText,
)


class TestJobManager(unittest.TestCase):
    """Test suite for JobManager persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.temp_dir.name)
        self.mgr = JobManager(storage_dir=self.storage_dir)

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


class TestAgentJobOrchestrator(unittest.TestCase):
    """Test suite for AgentJobOrchestrator."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = JobManager(storage_dir=Path(self.temp_dir.name))
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


if __name__ == "__main__":
    unittest.main()
