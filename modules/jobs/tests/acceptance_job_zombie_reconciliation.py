"""Acceptance tests for the zombie-reconciliation requirement.

The requirement in `modules/jobs/FRD.md` FR-JOBS-003 is that a record whose
worker died reaches a terminal state on the next pool start, so a poller
never waits on a job that will never finish. These seed a record owned by a
dead process and assert storage construction reconciles it.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.shared.src.taxonomy_core_vo import JobRecord


def _dead_worker_record(job_id: str, age_hours: int) -> JobRecord:
    """Return an incomplete record owned by a process that no longer exists.

    ``owner_pid`` is set to a pid above the current ``pid_max`` so it can
    never collide with a live process on the host.
    """
    stale = datetime.now(UTC) - timedelta(hours=age_hours)
    return JobRecord(
        job_id=job_id,
        created_at=stale.isoformat(),
        latest_event="GENERATION_STARTED",
        completed=False,
        owner_pid=os.sysconf("SC_OPEN_MAX") + job_id.__len__(),
        heartbeat_at=stale.isoformat(),
    )


def test_acceptance_a_fresh_zombie_is_not_reconciled(tmp_path: Path) -> None:
    storage = JobStorage(storage_dir=tmp_path)
    storage.save_job(_dead_worker_record("fresh-zombie", age_hours=0))

    assert storage.get_job("fresh-zombie") is not None


def test_acceptance_a_stale_zombie_is_moved_to_a_terminal_state(tmp_path: Path) -> None:
    storage = JobStorage(storage_dir=tmp_path)
    storage.save_job(_dead_worker_record("stale-zombie", age_hours=48))

    # Constructing a second storage instance runs reconciliation, which is
    # what a process restart does.
    reconciled = JobStorage(storage_dir=tmp_path).get_job("stale-zombie")

    assert reconciled is not None
    assert reconciled.completed is True, "a dead worker's record must reach a terminal state"


def test_acceptance_reconciliation_names_the_dead_worker_as_the_error(tmp_path: Path) -> None:
    storage = JobStorage(storage_dir=tmp_path)
    storage.save_job(_dead_worker_record("named-zombie", age_hours=48))

    reconciled = JobStorage(storage_dir=tmp_path).get_job("named-zombie")

    assert reconciled is not None
    assert reconciled.error, "a reconciled record must say why it stopped"


def test_acceptance_a_completed_record_is_left_alone(tmp_path: Path) -> None:
    storage = JobStorage(storage_dir=tmp_path)
    storage.save_job(
        JobRecord(
            job_id="done",
            created_at=datetime.now(UTC).isoformat(),
            completed=True,
            result_preview="ok",
        )
    )

    assert JobStorage(storage_dir=tmp_path).get_job("done").completed is True
