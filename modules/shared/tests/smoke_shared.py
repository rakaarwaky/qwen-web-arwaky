"""Smoke tests for shared module — fast verification that core imports and functions work."""

from __future__ import annotations

from modules.shared.src import AppConfig, RunContext, CircuitBreaker, RateLimiter
from modules.shared.src.utility_core_path import list_input_files, should_process_file
from modules.shared.src.utility_core_prompt import extract_prompt_text, strip_input_from_output


class TestSharedSmoke:
    """Fast smoke tests for shared module (must complete in <5s)."""

    def test_app_config_creation(self):
        cfg = AppConfig(base_url="http://test.com")
        assert cfg.base_url == "http://test.com"

    def test_run_context_creation(self):
        ctx = RunContext(session_id="test-session")
        assert ctx.session_id == "test-session"

    def test_extract_prompt_text_simple(self):
        assert extract_prompt_text("Hello world") == "Hello world"

    def test_extract_prompt_text_with_frontmatter(self):
        content = "---\ntitle: test\n---\nActual prompt"
        assert extract_prompt_text(content) == "Actual prompt"

    def test_should_process_file_matches(self):
        assert should_process_file("test.md") is True
        assert should_process_file("test.txt") is True
        assert should_process_file("test.jpg") is False

    def test_circuit_breaker_initial_state(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "closed"

    def test_rate_limiter_initial_state(self):
        rl = RateLimiter(max_tokens=10, window_seconds=60)
        assert rl.tokens == 10
