"""Jobs-domain aggregate contract (AES101 `_aggregate`).

``IJobManagerAggregate`` is the single entry point over the jobs feature.
The CLI and MCP surfaces call :meth:`execute`; the agent behind the
aggregate owns the submit → dispatch → wait → persist sequence, so no
surface can skip the admission or circuit-breaker guards that every job
submission depends on.

Operation-specific verbs live in the ``JobRequest.verb`` field; all
consumer arguments ride on ``JobRequest``, and the result shape is a
single ``JobResponse``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from modules.shared.src.taxonomy_jobs_vo import JobRequest, JobResponse


class IJobManagerAggregate(ABC):
    """Single entry point over the jobs feature.

    Exactly one method: the door consumers knock on. Adding a consumer
    verb means adding a variant to ``JobRequest.verb``, not a second
    aggregate method.
    """

    @abstractmethod
    def execute(self, request: JobRequest) -> JobResponse:
        """Run one job operation and return the result.

        Routes *request* to the matching capability operation and
        returns a single response VO. For submission verbs, the
        persisted ``JobRecord`` is returned as ``response.record``;
        for ``list_jobs``, the list is returned as ``response.records``;
        for ``shutdown``, the executor's final state is reported.
        """
        ...


__all__ = ["IJobManagerAggregate"]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IJobManagerAggregate": IJobManagerAggregate,
}
