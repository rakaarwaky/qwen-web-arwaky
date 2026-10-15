"""Update refusal policy (utility layer).

Fail-closed refusal helpers, split out of ``utility_update_pipeline.py``.
A release that cannot be pinned to an immutable commit SHA is refused
rather than installed from a mutable tag reference (issue #368), and a
smoke gate that cannot run reports a failing step instead of a pass.
"""

from __future__ import annotations

import logging

from modules.shared.src.common.taxonomy_core_vo import UpdateStepResult

__all__ = [
    "refuse_unverified_install",
    "smoke_gate_unavailable",
]

log = logging.getLogger("utility_update_refusal")


def refuse_unverified_install(target_version: str | None, mode: str) -> UpdateStepResult:
    """Fail-closed refusal when a release cannot be pinned to a commit SHA.

    Never falls back to a mutable tag reference (issue #368): installing
    unverifiable remote code is strictly worse than refusing the update.
    """
    detail = (
        f"{mode} refused: release {target_version!r} could not be pinned to an immutable "
        "commit SHA via the GitHub API; refusing to install unverified remote code. "
        "Check that the release tag exists and the network can reach api.github.com."
    )
    log.error("install_refused_unverified target=%s mode=%s", target_version, mode)
    return UpdateStepResult(name="package_upgrade", executed=False, success=False, detail=detail)


def smoke_gate_unavailable(reason: str) -> tuple[UpdateStepResult, ...]:
    """Return the failing health check emitted when the smoke gate itself errored."""
    log.warning("doctor_smoke_gate_unavailable reason=%s", reason)
    return (
        UpdateStepResult(
            name="smoke:doctor_gate",
            executed=True,
            success=False,
            detail=f"functional doctor gate could not run: {reason}",
        ),
    )
