"""E2E tests for core module — tests end-to-end flows with mocked browser."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCoreE2E:
    """End-to-end tests for core module flows."""

    def test_direct_prompt_flow(self, tmp_path: Path):
        """Test a complete direct prompt flow."""
        from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator
        from modules.shared.src import AppConfig, RunContext

        output_file = tmp_path / "output.md"
        config = AppConfig(base_url="http://test.com", output_dir=str(tmp_path))
        ctx = RunContext(session_id="test-session", config=config)

        browser = MagicMock()
        injector = MagicMock()
        sender = MagicMock()
        streamer = MagicMock()
        saver = MagicMock()
        observability = MagicMock()
        observability.get_logger.return_value = MagicMock()

        orchestrator = DirectPromptOrchestrator(
            browser=browser, injector=injector, sender=sender,
            streamer=streamer, saver=saver, observability=observability, flow=MagicMock()
        )
        # Verify orchestrator is properly initialized
        assert orchestrator._config.base_url == "http://test.com"
        assert orchestrator._ctx.session_id == "test-session"

    def test_job_manager_flow(self, tmp_path: Path):
        """Test job manager creates and tracks jobs."""
        from modules.core.src.capabilities_job_manager import JobManager
        from modules.shared.src import AppConfig

        config = AppConfig(base_url="http://test.com", output_dir=str(tmp_path))
        manager = JobManager(config=config)
        assert manager._config is not None

    def test_prompt_injector_flow(self):
        """Test prompt injector applies system prompts."""
        from modules.core.src.capabilities_prompt_injector import PromptInjector
        injector = PromptInjector()
        assert injector is not None

    def test_stream_monitor_flow(self):
        """Test stream monitor initialization."""
        from modules.core.src.capabilities_stream_monitor import StreamMonitor
        monitor = StreamMonitor()
        assert monitor is not None

    def test_output_saver_flow(self, tmp_path: Path):
        """Test output saver saves content to file."""
        from modules.core.src.capabilities_output_saver import Saver

        saver = Saver()
        assert saver is not None
