"""Thread-safety tests for the shared dispatch guards and job storage.

The system runs up to ``DEFAULT_MAX_WORKERS`` browser slots, so ``CircuitBreaker``,
``RateLimiter`` and ``JobManager`` are all exercised from several threads at once.
These tests use a ``threading.Barrier`` to make every worker reach the contended
call at the same instant, which is what makes an unsynchronized implementation
actually fail rather than merely being theoretically racy.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from modules.core.src.capabilities_job_manager import JobManager
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_vo import (
    FailureCategory,
    FailureThreshold,
    JobLimit,
    JobRecord,
    MaxPerMinute,
    WindowSec,
)

THREADS = 10


def _run_in_parallel(worker, count: int = THREADS) -> list[BaseException]:
    """Run ``worker(index)`` on ``count`` threads released simultaneously."""
    barrier = threading.Barrier(count)
    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def runner(index: int) -> None:
        barrier.wait()
        try:
            worker(index)
        except BaseException as exc:
            with errors_lock:
                errors.append(exc)

    threads = [threading.Thread(target=runner, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "worker threads did not finish"
    return errors


def test_circuit_breaker_counts_every_concurrent_failure() -> None:
    """No failure may be lost when all workers record at the same moment.

    A threshold above the worker count keeps the breaker open, so the assertion
    targets the thing a lock actually protects: that each ``record_failure``
    survives the prune-then-count sequence instead of being clobbered.
    """
    breaker = CircuitBreaker(FailureThreshold(THREADS + 1), WindowSec(30))

    errors = _run_in_parallel(lambda _: breaker.record_failure())

    assert not errors, f"unexpected exceptions: {errors}"
    assert len(breaker._failures) == THREADS
    assert not breaker.is_tripped


def test_circuit_breaker_trips_exactly_at_threshold() -> None:
    """The breaker must be open below the threshold and closed at it."""
    breaker = CircuitBreaker(FailureThreshold(THREADS), WindowSec(30))

    errors = _run_in_parallel(lambda _: breaker.record_failure())

    assert not errors, f"unexpected exceptions: {errors}"
    assert breaker.is_tripped


def test_circuit_breaker_survives_interleaved_success_and_failure() -> None:
    """Mixed record_success/record_failure must never corrupt internal state."""
    breaker = CircuitBreaker(FailureThreshold(3), WindowSec(30))

    def worker(index: int) -> None:
        for _ in range(50):
            if index % 2:
                breaker.record_failure()
            else:
                breaker.record_success()
            _ = breaker.is_tripped

    errors = _run_in_parallel(worker)

    assert not errors, f"unexpected exceptions: {errors}"


def test_rate_limiter_never_exceeds_cap_under_concurrent_acquire() -> None:
    """At most max_per_minute reservations may be handed out in one window."""
    limit = 5
    limiter = RateLimiter(MaxPerMinute(limit))
    granted: list[int] = []
    granted_lock = threading.Lock()

    def worker(index: int) -> None:
        # try_acquire never blocks, so every thread reports a verdict and the
        # test cannot hang even if the limiter is broken.
        if limiter.try_acquire() is None:
            with granted_lock:
                granted.append(index)

    errors = _run_in_parallel(worker)

    assert not errors, f"unexpected exceptions: {errors}"
    assert len(granted) == limit, f"limiter granted {len(granted)} slots, expected {limit}"


def test_rate_limiter_reports_retry_delay_when_exhausted() -> None:
    """A refused reservation must carry a positive retry hint."""
    limiter = RateLimiter(MaxPerMinute(1))

    assert limiter.try_acquire() is None
    wait_sec = limiter.try_acquire()

    assert wait_sec is not None
    assert wait_sec > 0


def test_job_manager_concurrent_writes_are_all_readable(tmp_path: Path) -> None:
    """Every concurrently saved record must survive and read back intact."""
    manager = JobManager(storage_dir=tmp_path / "jobs")

    def worker(index: int) -> None:
        for revision in range(10):
            manager.save_job(
                JobRecord(
                    job_id=f"job_{index}",
                    created_at="2026-09-22T00:00:00Z",
                    latest_event=f"rev_{revision}",
                )
            )

    errors = _run_in_parallel(worker)

    assert not errors, f"unexpected exceptions: {errors}"
    for index in range(THREADS):
        record = manager.get_job(f"job_{index}")
        assert record is not None, f"job_{index} was lost"
        assert record.latest_event == "rev_9"


def test_job_manager_list_jobs_tolerates_concurrent_writes(tmp_path: Path) -> None:
    """list_jobs must not raise while other threads are saving records."""
    manager = JobManager(storage_dir=tmp_path / "jobs")
    stop = threading.Event()

    def writer(index: int) -> None:
        if index != 0:
            while not stop.is_set():
                manager.save_job(JobRecord(job_id=f"job_{index}", created_at="2026-09-22T00:00:00Z", latest_event="x"))
            return
        try:
            for _ in range(50):
                # Partial reads would surface here as a JSON error.
                manager.list_jobs(JobLimit(10))
        finally:
            stop.set()

    errors = _run_in_parallel(writer)

    assert not errors, f"unexpected exceptions: {errors}"


@pytest.mark.parametrize(
    "job_id",
    [
        "../../escape",
        "with/slash",
        "with\\backslash",
        'colon:star*quote"pipe|',
        "a" * 400,
    ],
)
def test_job_file_path_stays_inside_storage_dir(tmp_path: Path, job_id: str) -> None:
    """Unsafe or oversized job IDs must not escape or overflow the filesystem."""
    storage = (tmp_path / "jobs").resolve()
    manager = JobManager(storage_dir=storage)

    path = manager._job_file_path(job_id).resolve()

    assert path.parent == storage
    assert len(path.name.encode("utf-8")) <= 255


def test_job_file_path_keeps_long_ids_distinct(tmp_path: Path) -> None:
    """Truncated long IDs must not collide with one another."""
    manager = JobManager(storage_dir=tmp_path / "jobs")

    first = manager._job_file_path("b" * 300 + "_one")
    second = manager._job_file_path("b" * 300 + "_two")

    assert first != second


def test_list_jobs_keeps_records_containing_temp_like_names(tmp_path: Path) -> None:
    """A real job whose ID resembles the temp-file marker must still be listed."""
    manager = JobManager(storage_dir=tmp_path / "jobs")
    manager.save_job(JobRecord(job_id="batch.tmp_cleanup", created_at="2026-09-22T00:00:00Z"))

    listed = {rec.job_id for rec in manager.list_jobs(JobLimit(10))}

    assert "batch.tmp_cleanup" in listed


# ── Categorised failure tracking (issue #340, AC4) ──────────────────────────


def test_circuit_breaker_counts_concurrent_categorised_failures() -> None:
    """Every concurrent ``record_failure(category)`` must land in the tally.

    The category deque is appended under the same lock that prunes the failure
    deque, so a worker that interleaves with ``_refresh_state`` must neither be
    dropped nor counted twice.
    """
    categories = ("network", "auth", "browser", "file_io")
    expected: dict[str, int] = {}
    for index in range(THREADS):
        name = categories[index % len(categories)]
        expected[name] = expected.get(name, 0) + 1

    breaker = CircuitBreaker(FailureThreshold(THREADS + 1), WindowSec(30))
    errors = _run_in_parallel(lambda i: breaker.record_failure(FailureCategory(categories[i % len(categories)])))

    assert not errors
    assert breaker.failure_categories == expected


def test_circuit_breaker_trip_reports_dominant_error_category() -> None:
    """A single-category window names its category so the trip is explainable."""
    breaker = CircuitBreaker(FailureThreshold(3), WindowSec(30))
    for _ in range(3):
        breaker.record_failure(FailureCategory("network"))

    assert breaker.is_tripped
    assert breaker.trip_category == "network"


def test_circuit_breaker_trip_category_is_none_for_mixed_failures() -> None:
    """Two distinct categories have no single cause, so none is reported."""
    breaker = CircuitBreaker(FailureThreshold(2), WindowSec(30))
    breaker.record_failure(FailureCategory("network"))
    breaker.record_failure(FailureCategory("auth"))

    assert breaker.is_tripped
    assert breaker.trip_category is None
