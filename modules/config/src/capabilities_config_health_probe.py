"""Capabilities: config health probe (AES403).

Implements the doctor smoke gate as a Capabilities-layer module so the Root
container and the update pipeline's postflight functional gate depend only
on an injected callable, never on the CLI Surface (issue #506).

The callable signature matches ``ISmokeGate``:
``Callable[[], tuple[tuple[str, bool, str], ...]]`` — a no-arg function
returning ``(name, passed, detail)`` triples.

Root composes ``build_smoke_gate(session)`` with a live ``ISessionAggregate``
at container-construction time. The returned gate re-runs the doctor checks
at gate-execution time so a post-update gate reflects the post-upgrade state
rather than the pre-upgrade one.

The diagnostic check bodies (``_check_python``, ``_check_chromium``, ...)
remain in the CLI Surface where their operator-report semantics belong;
this module is the functional-seam wrapper that the update pipeline
consumes through dependency injection.
"""

from __future__ import annotations

from collections.abc import Callable

from modules.cli.src.surface_cli_doctor_command import run_doctor_checks
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate


def build_smoke_gate(
    session: ISessionAggregate,
) -> Callable[[], tuple[tuple[str, bool, str], ...]]:
    """Return a callable the update pipeline runs as its postflight functional gate.

    Returns the non-interactive diagnostic checks as ``(name, passed, detail)``
    triples. The Root layer composes this so the Capabilities update pipeline
    depends only on an injected callable, never on a Surface. The checks run
    at gate-execution time (not container-construction time) so the post-update
    gate reflects the post-upgrade state (issue #506).

    Pass the aggregate, e.g. ``session_manager.load_pool()`` or a production
    ``ISessionAggregate`` — there is no default, so a wiring gap cannot
    masquerade as an empty pool.
    """
    aggregate = session

    def _gate() -> tuple[tuple[str, bool, str], ...]:
        checks = run_doctor_checks(session=aggregate)
        return tuple((str(check["name"]), bool(check["passed"]), str(check["detail"])) for check in checks)

    return _gate


__all__ = [
    "build_smoke_gate",
]
