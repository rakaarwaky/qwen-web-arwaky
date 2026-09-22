"""Regression tests for types module — LifecycleEmitter, CircuitBreaker, RateLimiter, AppConfig validation."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.shared.src import (
    AppConfig,
    CircuitBreaker,
    LifecycleEmitter,
    QwenEventType,
    RateLimiter,
    RunContext,
)

# ─── LifecycleEmitter ───────────────────────────────────────────────────────


class TestLifecycleEmitter:
    def test_emit_returns_event(self):
        emitter = LifecycleEmitter()
        evt = emitter.emit("test_event")
        assert evt.name == "test_event"
        assert evt.details == {}

    def test_emit_with_details(self):
        emitter = LifecycleEmitter()
        evt = emitter.emit("test", {"key": "value"})
        assert evt.details == {"key": "value"}

    def test_callback_called(self):
        emitter = LifecycleEmitter()
        received = []
        emitter.on("test", lambda e: received.append(e))
        emitter.emit("test")
        assert len(received) == 1

    def test_multiple_callbacks(self):
        emitter = LifecycleEmitter()
        calls = [0, 0]
        emitter.on("test", lambda e: calls.__setitem__(0, calls[0] + 1))
        emitter.on("test", lambda e: calls.__setitem__(1, calls[1] + 1))
        emitter.emit("test")
        assert calls == [1, 1]

    def test_different_events(self):
        emitter = LifecycleEmitter()
        a_calls = []
        b_calls = []
        emitter.on("event_a", lambda e: a_calls.append(1))
        emitter.on("event_b", lambda e: b_calls.append(1))
        emitter.emit("event_a")
        assert len(a_calls) == 1
        assert len(b_calls) == 0

    def test_callback_exception_does_not_break_emit(self):
        emitter = LifecycleEmitter()
        emitter.on("test", lambda e: 1 / 0)
        emitter.on("test", lambda e: None)
        # Should not raise — callback error is caught
        emitter.emit("test")

    def test_enum_event_type(self):
        emitter = LifecycleEmitter()
        evt = emitter.emit(QwenEventType.THINKING_STARTED)
        assert "THINKING_STARTED" in evt.name

    def test_event_has_unique_id(self):
        emitter = LifecycleEmitter()
        e1 = emitter.emit("test")
        e2 = emitter.emit("test")
        assert e1.event_id != e2.event_id

    def test_event_has_timestamp(self):
        emitter = LifecycleEmitter()
        before = time.time()
        evt = emitter.emit("test")
        after = time.time()
        assert before <= evt.timestamp <= after

    def test_callback_error_is_recorded_and_logged(self):
        logger = MagicMock()
        emitter = LifecycleEmitter(logger=logger)

        def failing_cb(evt):
            raise ValueError("callback failed intentionally")

        emitter.on("test", failing_cb)
        evt = emitter.emit("test")
        assert evt.name == "test"
        assert len(emitter.callback_errors) == 1
        assert emitter.callback_errors[0]["event"] == "test"
        assert "callback failed intentionally" in emitter.callback_errors[0]["error"]
        assert emitter.callback_errors[0]["type"] == "ValueError"
        assert logger.error.called


# ─── CircuitBreaker edge cases ─────────────────────────────────────────────


class TestCircuitBreakerExtended:
    def test_threshold_1_trips_immediately(self):
        cb = CircuitBreaker(threshold=1, window_sec=30)
        cb.record_failure()
        assert cb.is_tripped is True

    def test_sliding_window_expires(self):
        cb = CircuitBreaker(threshold=3, window_sec=1)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_tripped is False
        # Manually age the first failure outside the window
        cb._failures[0] = time.time() - 2
        cb.record_failure()  # evicts old failure, adds new = 2 in window
        assert len(cb._failures) == 2
        assert cb.is_tripped is False  # threshold=3, only 2 in window

    def test_success_resets_after_partial_failures(self):
        cb = CircuitBreaker(threshold=3, window_sec=30)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_tripped is False
        cb.record_success()
        assert cb.is_tripped is False
        cb.record_failure()
        assert cb.is_tripped is False

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            CircuitBreaker(threshold=0)

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError, match="window_sec"):
            CircuitBreaker(window_sec=0)


# ─── RateLimiter throttling ────────────────────────────────────────────────


class TestRateLimiterExtended:
    def test_acquire_multiple(self):
        rl = RateLimiter(max_per_minute=5)
        for _ in range(5):
            rl.acquire()
        assert len(rl._timestamps) == 5

    def test_throttles_when_exceeded(self):
        from collections import deque

        rl = RateLimiter(max_per_minute=2)
        # Pre-seed timestamps inside the mocked window (time=100, window=40..100)
        # so the rate limiter sees the bucket as full from the start of the patch.
        rl._timestamps = deque([70.0, 80.0])
        with patch("modules.shared.src.taxonomy_core_entity.time") as mock_time:
            # After sleep, advance time past the window so the oldest evicts.
            mock_time.time.side_effect = [100.0, 100.0, 100.0, 161.0, 161.0]
            mock_time.sleep = MagicMock()
            rl.acquire()
            mock_time.sleep.assert_called()

    def test_invalid_max_per_minute_raises(self):
        with pytest.raises(ValueError, match="max_per_minute"):
            RateLimiter(max_per_minute=0)


# ─── AppConfig validation ──────────────────────────────────────────────────


class TestAppConfigValidation:
    def _make_cfg(self, **kwargs):
        defaults = dict(
            mode="batch",
            input_path=Path("/tmp/input"),
            output_path=Path("/tmp/output"),
            session_path=Path("/tmp/session"),
        )
        defaults.update(kwargs)
        return AppConfig(**defaults)

    def test_valid_config_passes(self):
        cfg = self._make_cfg()
        assert cfg.validate() is None

    def test_timeout_too_low_raises(self):
        with pytest.raises(ValueError, match="timeout"):
            self._make_cfg(timeout=10)

    def test_poll_interval_too_low_raises(self):
        with pytest.raises(ValueError, match="poll_interval"):
            self._make_cfg(poll_interval=0.1)

    def test_request_timeout_too_low_raises(self):
        with pytest.raises(ValueError, match="request_timeout"):
            self._make_cfg(request_timeout=5)

    def test_rate_limit_zero_raises(self):
        with pytest.raises(ValueError, match="rate_limit_per_minute"):
            self._make_cfg(rate_limit_per_minute=0)

    def test_circuit_breaker_threshold_low_raises(self):
        with pytest.raises(ValueError, match="circuit_breaker_threshold"):
            self._make_cfg(circuit_breaker_threshold=1)

    def test_status_path(self):
        cfg = self._make_cfg(log_path=Path("/var/log"))
        assert cfg.status_path == Path("/var/log/status.json")


# ─── RunContext ────────────────────────────────────────────────────────────


class TestRunContextExtended:
    def test_run_id_format(self):
        ctx = RunContext()
        assert len(ctx.run_id) > 10
        assert "_" in ctx.run_id

    def test_run_id_uniqueness(self):
        ids = {RunContext().run_id for _ in range(100)}
        assert len(ids) == 100
