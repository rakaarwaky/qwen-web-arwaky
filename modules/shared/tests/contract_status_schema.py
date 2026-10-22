"""Contract: the status.json document shape for schema version 2.

External monitors branch on ``schema_version`` and read a fixed key set
(FR-JOBS-002 / FR-LOGGING-001), so a dropped or renamed field breaks them
silently. Pins both the base document and the fully-populated variant
``StatusFileWriter.write`` emits.
"""

from __future__ import annotations

from pathlib import Path

from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.shared.src.common.taxonomy_core_constant import STATUS_SCHEMA_VERSION

#: Keys every status.json carries, whatever the run did.
BASE_KEYS = frozenset(
    {
        "schema_version",
        "updated_at",
        "status",
        "mode",
        "headless",
        "run_id",
        "files_processed",
        "files_failed",
        "failure_categories",
    }
)

#: The fully-populated schema-version-2 document: base keys plus every
#: optional field present in one representative call.
FULL_KEYS = BASE_KEYS | {"metrics", "cpu_sec", "error"}


def test_base_document_pins_the_schema_version_2_key_set(tmp_path: Path) -> None:
    writer = StatusFileWriter(tmp_path / "status.json")
    writer.write(status="running", mode="single", headless=True, run_id="run-1")

    doc = writer.read()

    assert doc is not None
    assert doc["schema_version"] == STATUS_SCHEMA_VERSION == 2
    assert frozenset(doc) == BASE_KEYS


def test_full_document_pins_every_optional_key(tmp_path: Path) -> None:
    writer = StatusFileWriter(tmp_path / "status.json")
    writer.write(
        status="failed",
        mode="single",
        headless=False,
        run_id="run-1",
        files_processed=3,
        files_failed=1,
        cpu_sec=12.345,
        error="boom",
        metrics={"total_executions": 5},
        failure_categories={"network": 2},
    )

    doc = writer.read()

    assert doc is not None
    assert frozenset(doc) == FULL_KEYS
    assert doc["cpu_sec"] == 12.35
    assert doc["metrics"]["total_executions"] == 5
    assert doc["failure_categories"] == {"network": 2}
    assert doc["error"] == "boom"


def test_optional_fields_are_omitted_not_nulled(tmp_path: Path) -> None:
    """Absent optionals must not appear as null keys a monitor must skip."""
    writer = StatusFileWriter(tmp_path / "status.json")
    writer.write(status="running", mode="single", headless=True, run_id="run-1")

    doc = writer.read()

    assert doc is not None
    assert "metrics" not in doc
    assert "cpu_sec" not in doc
    assert "error" not in doc
