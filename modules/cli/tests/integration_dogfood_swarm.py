"""Dogfood swarm pipeline tests — structure validation for swarm orchestration.

These tests verify the swarm pipeline structure and templates:
1. Role templates are discoverable
2. Output structure is correct

NEVER RUNS API CALLS — structure tests only.
Real API validation: run pytest --run-dogfood with live Qwen session.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.shared.src.utility_core_prompt_template import list_prompt_templates


class TestSwarmPipelineStructure:
    """Test swarm pipeline structure and discoverability."""

    def test_swarm_templates_discoverable(self):
        """Verify role templates are discoverable."""
        templates = list_prompt_templates()
        assert len(templates) > 0, "No prompt templates discovered"
        print(f"\n[SWARM] Discovered {len(templates)} role templates: {templates}")

    def test_swarm_concurrency_config(self):
        """Verify swarm concurrency is capacity-derived and capped (issue #291)."""
        from modules.shared.src.taxonomy_core_constant import DEFAULT_MAX_WORKERS
        from modules.shared.src.utility_core_capacity import recommended_max_workers
        from modules.swarm.src.capabilities_swarm_runner import SwarmRunner

        assert DEFAULT_MAX_WORKERS == 10
        capacity = recommended_max_workers()
        assert 1 <= capacity <= DEFAULT_MAX_WORKERS
        print(f"\n[SWARM-TEST] Concurrency: capacity {capacity} / cap {DEFAULT_MAX_WORKERS}")

        runner = SwarmRunner(attachment=MagicMock(), browser_concurrency=DEFAULT_MAX_WORKERS + 5)
        assert int(runner.browser_concurrency) <= capacity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
