"""Integration tests for job storage against a real filesystem.

These read and write real JSON records under a temporary directory, so the
atomic write, the not-found path, and the listing order are exercised
against the filesystem rather than a stub.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.shared.src.taxonomy_core_vo import JobRecord


def _record(job_id: str) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        created_at=datetime.now(UTC).isoformat(),
        latest_event="GENERATION_STARTED",
    )


def test_integration_a_saved_record_round_trips_through_the_filesystem(tmp_path: Path) -> None:
    storage = JobStorage(storage_dir=tmp_path)
    storage.save_job(_record("round-trip"))

    loaded = storage.get_job("round-trip")

    assert loaded is not None
    assert loaded.job_id == "round-trip"
    assert loaded.latest_event == "GENERATION_STARTED"


def test_integration_an_unknown_identifier_reads_back_as_nothing(tmp_path: Path) -> None:
    storage = JobStorage(storage_dir=tmp_path)

    assert storage.get_job("never-submitted") is None


def test_integration_listing_returns_the_saved_records_newest_first(tmp_path: Path) -> None:
    storage = JobStorage(storage_dir=tmp_path)
    for job_id in ("first", "second", "third"):
        storage.save_job(_record(job_id))

    listed = storage.list_jobs(limit=10)

    assert [record.job_id for record in listed] == ["third", "second", "first"]


def test_integration_a_missing_storage_directory_is_created(tmp_path: Path) -> None:
    target = tmp_path / "not" / "there" / "yet"

    storage = JobStorage(storage_dir=target)
    storage.save_job(_record("created-dir"))

    assert storage.get_job("created-dir") is not None
