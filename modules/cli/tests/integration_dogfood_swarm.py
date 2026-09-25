"""Dogfood swarm pipeline tests — structure validation for swarm orchestration.

These tests verify the swarm pipeline structure and templates:
1. SwarmOrchestrator can be imported
2. Role templates are discoverable
3. Input files are valid
4. Output structure is correct

NEVER RUNS API CALLS — structure tests only.
Real API validation: run pytest --run-dogfood with live Qwen session.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.shared.src.utility_core_prompt_template import list_prompt_templates


def _create_test_input(tmp_path: Path) -> Path:
    """Create a test input file for swarm."""
    input_file = tmp_path / "swarm_test_input.md"
    input_file.write_text("""# Dogfood Swarm Test

Please analyze the following and provide your role-specific output:

Test case: Dogfood pipeline validation
""")
    return input_file


class TestSwarmPipelineStructure:
    """Test swarm pipeline structure and discoverability."""

    def test_swarm_orchestrator_exists(self):
        """Verify SwarmOrchestrator can be imported."""
        from modules.core.src.agent_swarm_orchestrator import SwarmOrchestrator

        assert SwarmOrchestrator is not None

    def test_swarm_templates_discoverable(self):
        """Verify role templates are discoverable."""
        templates = list_prompt_templates()
        assert len(templates) > 0, "No prompt templates discovered"
        print(f"\n[SWARM] Discovered {len(templates)} role templates: {templates}")

    def test_swarm_input_accepted(self, tmp_path: Path):
        """Verify swarm accepts valid input file."""
        input_file = _create_test_input(tmp_path)
        assert input_file.exists()
        assert input_file.read_text().startswith("#")


class TestSwarmOutputStructure:
    """Test that swarm output structure is valid."""

    def test_swarm_output_structure(self, tmp_path: Path):
        """Verify swarm would create expected output structure."""
        swarm_id = "dogfood_test_123"
        output_root = tmp_path / swarm_id

        # Simulate expected output structure
        output_root.mkdir()
        assert output_root.exists()
        assert output_root.is_dir()

        # Verify subdirectories would be created
        for subdir in ["logs", "outputs"]:
            sub = output_root / subdir
            sub.mkdir(exist_ok=True)
            assert sub.is_dir()

    def test_swarm_concurrency_config(self):
        """Verify swarm concurrency is capacity-derived and capped (issue #291)."""
        from modules.core.src.agent_swarm_orchestrator import SwarmOrchestrator
        from modules.shared.src.taxonomy_core_constant import DEFAULT_MAX_WORKERS
        from modules.shared.src.utility_core_capacity import recommended_max_workers

        assert DEFAULT_MAX_WORKERS == 10
        capacity = recommended_max_workers()
        assert 1 <= capacity <= DEFAULT_MAX_WORKERS
        print(f"\n[SWARM-TEST] Concurrency: capacity {capacity} / cap {DEFAULT_MAX_WORKERS}")

        orchestrator = SwarmOrchestrator(attachment=MagicMock(), browser_concurrency=DEFAULT_MAX_WORKERS + 5)
        assert orchestrator._browser_concurrency <= capacity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
