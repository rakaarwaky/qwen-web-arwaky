"""Update-domain value objects and aggregate request/response pair.

The update feature owns version discovery, package and browser
synchronisation, and the rollback path that restores the previous
release when the post-update health gate fails. Consumers depend on one
seam: the aggregate's ``execute`` takes an ``UpdateRequest`` and returns
an ``UpdateResponse``. Operation-specific arguments ride on the request;
the capability result of each verb rides on the response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)

#: Which update operation an ``UpdateRequest`` asks for. The agent behind
#: ``IUpdateAggregate`` routes each one to the matching capability method.
UpdateVerb: TypeAlias = Literal[
    "current_version",
    "check_update",
    "upgrade_package",
    "sync_browser",
    "perform_update",
    "rollback_to",
]

#: The ordered per-step outcomes a rollback recorded, in execution order.
RollbackSteps: TypeAlias = tuple[UpdateStepResult, ...]


@dataclass(frozen=True)
class UpdateRequest:
    """One update verb plus everything the agent needs to run it.

    Fields the chosen verb does not read stay at their defaults, so the
    pipeline verbs and the rollback verb share one shape without either
    passing arguments the other ignores.
    """

    verb: UpdateVerb
    force: ForceFlag = ForceFlag(False)
    previous_version: VersionString | str | None = None


@dataclass(frozen=True)
class UpdateResponse:
    """What an update verb produced.

    ``check_result`` / ``step_result`` / ``report`` carry the result of
    the respective verb; ``version`` carries the bare ``current_version``
    answer; ``steps`` carries the ordered rollback outcomes. ``error``
    names the reason a request could not be answered at all.
    """

    version: VersionString | str | None = None
    check_result: UpdateCheckResult | None = None
    step_result: UpdateStepResult | None = None
    report: UpdateReport | None = None
    steps: tuple[UpdateStepResult, ...] = ()
    error: str | None = None


__all__ = [
    "RollbackSteps",
    "UpdateRequest",
    "UpdateResponse",
    "UpdateVerb",
]
