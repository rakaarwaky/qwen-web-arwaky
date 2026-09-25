"""Backpressure tests for the bounded async job queue (issue #362).

``AgentJobOrchestrator`` must refuse over-capacity submissions with a
structured, retryable error instead of growing the executor's pending queue
without bound, and it must never park the submitting thread waiting for a
rate-limit slot. A blocked submit would hang an MCP client with no diagnostic,
which is the failure mode these tests pin shut.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.agent_job_orchestrator import AgentJobOrchestrator
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_error import CircuitBreakerOpenError, JobQueueFullError
from modules.shared.src.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec


def _orchestrator(tmp_path: Path, max_workers: int, **kwargs) -> AgentJobOrchestrator:
    """Build an orchestrator whose workers never actually run a browser."""
    storage = MagicMock()
    storage.save_job.return_value = None
    blocked = threading.Event()

    def _block_forever(*_args, **_kwargs) -> None:
        blocked.wait(timeout=30)

    return AgentJobOrchestrator(
        storage=storage,
        file_only=MagicMock(process_prompt_file_only=_block_forever),
        attachment=MagicMock(process_prompt_with_attachment=_block_forever),
        max_workers=max_workers,
        **kwargs,
    )


def test_default_capacity_covers_running_and_queued_work(tmp_path: Path) -> None:
    """One pending slot per worker is the default backlog, not an open queue."""
    orchestrator = _orchestrator(tmp_path, max_workers=2)

    try:
        assert orchestrator.max_pending_jobs() == 4
    finally:
        orchestrator.shutdown()


def test_submission_beyond_capacity_is_refused_with_retry_hint(tmp_path: Path) -> None:
    """An over-capacity submit raises a retryable error, never a silent queue."""
    orchestrator = _orchestrator(tmp_path, max_workers=1, max_pending_jobs=1)

    try:
        prompt = tmp_path / "p.md"
        prompt.write_text("hello", encoding="utf-8")
        orchestrator.submit_file_job(prompt)
        # The single slot is now held by a worker that never finishes.
        with pytest.raises(JobQueueFullError) as caught:
            orchestrator.submit_file_job(prompt)

        assert caught.value.retry_after_sec is not None
        assert float(caught.value.retry_after_sec) > 0
        assert "capacity" in str(caught.value).lower()
    finally:
        orchestrator.shutdown()


def test_refused_submission_persists_no_job_record(tmp_path: Path) -> None:
    """A refused submit must leave no orphan record that no worker will claim."""
    orchestrator = _orchestrator(tmp_path, max_workers=1, max_pending_jobs=1)
    storage = orchestrator._storage

    try:
        prompt = tmp_path / "p.md"
        prompt.write_text("hello", encoding="utf-8")
        orchestrator.submit_file_job(prompt)
        saved_before = storage.save_job.call_count

        with pytest.raises(JobQueueFullError):
            orchestrator.submit_file_job(prompt)

        assert storage.save_job.call_count == saved_before
    finally:
        orchestrator.shutdown()


def test_queue_depth_tracks_admitted_work(tmp_path: Path) -> None:
    """Queue depth is observable so callers can report over-capacity state."""
    orchestrator = _orchestrator(tmp_path, max_workers=2, max_pending_jobs=2)

    try:
        assert orchestrator.queue_depth() == 0
        prompt = tmp_path / "p.md"
        prompt.write_text("hello", encoding="utf-8")
        orchestrator.submit_file_job(prompt)
        assert orchestrator.queue_depth() == 1
    finally:
        orchestrator.shutdown()


def test_exhausted_rate_limiter_does_not_block_the_submitting_thread(tmp_path: Path) -> None:
    """Rate limiting throttles the worker, so submit never waits on a timer.

    The submit path is the MCP tool caller's thread: it must return a
    ``JobRecord`` in bounded time.  Throughput is therefore enforced at dispatch
    time on the worker (which blocks on ``_guard_dispatch``), and the limiter is
    charged exactly once per job.
    """
    limiter = RateLimiter(MaxPerMinute(1))
    assert limiter.try_acquire() is None  # the only slot is already taken
    orchestrator = _orchestrator(tmp_path, max_workers=1, rate_limiter=limiter)

    try:
        prompt = tmp_path / "p.md"
        prompt.write_text("hello", encoding="utf-8")
        submitted: list[object] = []
        errors: list[BaseException] = []

        def _submit() -> None:
            try:
                submitted.append(orchestrator.submit_file_job(prompt))
            except BaseException as exc:
                errors.append(exc)

        caller = threading.Thread(target=_submit)
        caller.start()
        caller.join(timeout=10)

        assert not caller.is_alive(), "submit blocked on the rate limiter instead of returning"
        assert not errors, f"submit raised: {errors}"
        assert len(submitted) == 1
    finally:
        orchestrator.shutdown()


def test_rate_limited_rejection_returns_the_slot_to_admission_control(tmp_path: Path) -> None:
    """A guard rejection must not consume a queue slot permanently.

    Admission is checked before both guards; when the submit-time guard
    (``_guard_submit``, the circuit breaker) refuses, the reserved slot is
    returned so the next submission is admitted rather than queue-full forever.
    """
    orchestrator = _orchestrator(
        tmp_path,
        max_workers=1,
        max_pending_jobs=1,
        circuit_breaker=CircuitBreaker(FailureThreshold(1), WindowSec(60)),
    )

    try:
        prompt = tmp_path / "p.md"
        prompt.write_text("hello", encoding="utf-8")
        # The breaker is open from the start, so the very first submit is refused.
        orchestrator._circuit_breaker.record_failure()

        with pytest.raises(CircuitBreakerOpenError):
            orchestrator.submit_file_job(prompt)
        # The slot was released, so the next submit is admitted past admission
        # control and refused by the same guard — not by JobQueueFullError.
        with pytest.raises(CircuitBreakerOpenError):
            orchestrator.submit_file_job(prompt)
        assert orchestrator.queue_depth() == 0
    finally:
        orchestrator.shutdown()
