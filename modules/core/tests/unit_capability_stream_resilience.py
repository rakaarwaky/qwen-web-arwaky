"""Unit tests for 10/10 error handling & resilience coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.core.src.capabilities_stream_monitor import validate_response_content
from modules.shared.src import (
    AuthRequiredError,
    CircuitBreaker,
    OutputValidationError,
    OutputWriteError,
    RateLimiter,
    RunContext,
)
from tests.helpers import write_output


def test_validate_response_content_valid():
    validate_response_content("This is a valid response from Qwen AI.")


def test_validate_response_content_empty():
    with pytest.raises(OutputValidationError, match="Response content is empty"):
        validate_response_content("   ")


def test_validate_response_content_captcha():
    with pytest.raises(AuthRequiredError, match="CAPTCHA"):
        validate_response_content("Please verify you are human to proceed.")


def test_validate_response_content_server_error():
    with pytest.raises(OutputValidationError, match="Server error"):
        validate_response_content("502 Bad Gateway - Nginx")


def test_circuit_breaker_tripping():
    cb = CircuitBreaker(threshold=3, window_sec=30)
    assert not cb.is_tripped

    cb.record_failure()
    cb.record_failure()
    assert not cb.is_tripped

    cb.record_failure()
    assert cb.is_tripped

    cb.record_success()
    assert not cb.is_tripped


def test_rate_limiter_acquisition():
    rl = RateLimiter(max_per_minute=10)
    rl.acquire()
    assert len(rl._timestamps) == 1


def test_saver_error_handling(tmp_path: Path):
    ctx = RunContext()
    invalid_file = Path("/proc/nonexistent_dir_12345/output.md")

    # atomic_write=False so the non-atomic path wraps OSError in OutputWriteError
    with pytest.raises(OutputWriteError, match="Failed to write output file"):
        write_output(invalid_file, "test content", ctx, "src.md", 1.0, 10, 12, config={"atomic_write": False})
