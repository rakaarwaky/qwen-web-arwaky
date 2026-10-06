"""Contract tests for the job capability's public seam.

Pins the aggregate and protocol surface a caller may depend on, so a
signature change fails here rather than in a caller that has to be reworked.
"""

from __future__ import annotations

import inspect

from modules.jobs.src.capabilities_job_storage import JobStorage
from modules.jobs.src.capabilities_status_writer import StatusFileWriter
from modules.shared.src.contract_core_protocol import IStatusProtocol
from modules.shared.src.contract_jobs_aggregate import IJobManagerAggregate
from modules.shared.src.contract_jobs_protocol import IJobStorageProtocol

_REQUIRED_PROTOCOLS: tuple[type, ...] = (IJobStorageProtocol, IStatusProtocol)


def test_storage_implements_the_storage_protocol() -> None:
    assert IJobStorageProtocol in inspect.getmro(JobStorage)


def test_status_writer_implements_the_status_protocol() -> None:
    assert IStatusProtocol in inspect.getmro(StatusFileWriter)


def test_aggregate_declares_only_the_execute_door() -> None:
    public = {name for name, _ in inspect.getmembers(IJobManagerAggregate, predicate=inspect.isfunction)}
    assert public == {"execute"}


def test_every_protocol_method_is_abstract_with_a_return_annotation() -> None:
    for protocol in _REQUIRED_PROTOCOLS:
        for name, _ in inspect.getmembers(protocol, predicate=inspect.isfunction):
            signature = inspect.signature(getattr(protocol, name))
            assert signature.return_annotation is not inspect.Signature.empty, (
                f"{protocol.__name__}.{name} has no return"
            )
