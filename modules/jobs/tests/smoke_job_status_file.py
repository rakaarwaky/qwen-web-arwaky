"""Smoke tests for the job manager's status file seam.

The status file is the inter-process handoff an external monitor polls, so
the smoke path is "write it, read it back, tolerate its absence". These run
against a real file under a temporary directory.
"""

from __future__ import annotations

from pathlib import Path

from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.shared.src.taxonomy_core_vo import StatusRecordVO


def _record() -> StatusRecordVO:
    return StatusRecordVO(status="running", mode="single", headless=True, files_processed=1)


def test_smoke_a_written_status_file_reads_back(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    writer = StatusFileWriter(status_path)

    writer.write_record(_record())
    read_back = writer.read()

    assert status_path.exists()
    assert read_back is not None
    assert read_back["status"] == "running"
    assert read_back["files_processed"] == 1


def test_smoke_an_absent_status_file_reads_back_as_nothing(tmp_path: Path) -> None:
    assert StatusFileWriter(tmp_path / "never-written.json").read() is None


def test_smoke_an_invalid_status_file_reads_back_as_nothing(tmp_path: Path) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text("{not json", encoding="utf-8")

    assert StatusFileWriter(status_path).read() is None
