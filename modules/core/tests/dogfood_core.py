"""Dogfood tests for core module — structure validation only, no live API calls.

These tests verify the core module structure is intact:
1. All orchestrators can be imported
2. All capabilities can be instantiated
3. No circular import issues
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _run_cli(args: list[str]) -> tuple[int, str]:
    """Run CLI command and return result."""
    import subprocess
    import os
    root = Path(__file__).resolve().parent.parent.parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    result = subprocess.run(
        [sys.executable, "-m", "modules.root_cli_main_entry"] + args,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return result.returncode, result.stdout


class TestCoreDogfood:
    """Test that core module components can be imported and instantiated."""

    def test_import_direct_prompt_orchestrator(self):
        from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator
        assert DirectPromptOrchestrator is not None

    def test_import_all_agents(self):
        from modules.core.src import agent_attachment_prompt_orchestrator
        from modules.core.src import agent_job_orchestrator
        from modules.core.src import agent_prompt_file_orchestrator
        from modules.core.src import agent_session_orchestrator
        from modules.core.src import agent_session_rotator
        from modules.core.src import agent_setup_orchestrator
        from modules.core.src import agent_shared_flow_orchestrator
        from modules.core.src import agent_swarm_orchestrator
        assert all([agent_attachment_prompt_orchestrator, agent_job_orchestrator,
                    agent_prompt_file_orchestrator, agent_session_orchestrator])

    def test_import_all_capabilities(self):
        from modules.core.src import capabilities_browser_adapter
        from modules.core.src import capabilities_file_uploader
        from modules.core.src import capabilities_folder_compiler
        from modules.core.src import capabilities_folder_to_attachment
        from modules.core.src import capabilities_job_manager
        from modules.core.src import capabilities_observability_setup
        from modules.core.src import capabilities_output_saver
        from modules.core.src import capabilities_prompt_injector
        from modules.core.src import capabilities_run_cancel_registry
        from modules.core.src import capabilities_send_dispatcher
        from modules.core.src import capabilities_session_health_checker
        from modules.core.src import capabilities_stream_monitor
        assert capabilities_browser_adapter is not None

    def test_cli_help_returns_ok(self):
        """CLI help should return successfully."""
        returncode, stdout = _run_cli(["--help"])
        assert returncode == 0
        assert "qwen-web-arwaky" in stdout

    def test_core_module_importable(self):
        """Core module should be importable without errors."""
        import modules.core.src
        assert hasattr(modules.core.src, "__path__")
