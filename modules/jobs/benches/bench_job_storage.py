"""Benchmark for job record persistence.

Uses time.perf_counter for measuring performance without requiring the
pytest-benchmark plugin. The storage runs against a temporary directory, so
the benchmark needs no network and no live job pool.
"""

from __future__ import annotations

import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.shared.src.taxonomy_core_vo import JobRecord

pytestmark = pytest.mark.benchmark


def bench_save_and_load(iterations: int = 200) -> float:
    """Benchmark one save-then-load round trip for a job record."""
    with tempfile.TemporaryDirectory() as tmp:
        storage = JobStorage(storage_dir=Path(tmp))
        record = JobRecord(
            job_id="bench-0001",
            created_at=datetime.now(UTC).isoformat(),
        )

        start = time.perf_counter()
        for _ in range(iterations):
            storage.save_job(record)
            storage.get_job("bench-0001")
        elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


def test_bench_save_and_load() -> None:
    """Report benchmark results for a job record round trip."""
    micros = bench_save_and_load()
    print(f"\n[BENCHMARK] job save+load: {micros:.2f} µs/round-trip")
    assert micros > 0
