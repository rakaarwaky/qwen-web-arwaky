"""Capabilities: config health probe (AES403).

Implements ``IConfigHealthProbeProtocol``.

The functional health gate the update pipeline runs as its post-update
verification step (FR-UPDATE-003, issue #294 / #506). Extracted from the
CLI doctor surface so this capability — not a Surface symbol — is what the
Root layer wires into the *capabilities* update pipeline, keeping the
dependency one-way between the two layers.

The gate composes the same non-interactive doctor checks the operator's
``doctor`` report runs, so the post-update gate and the operator report can
never disagree about which checks pass. The checks run at gate-execution
time, not at container-construction time, so a gate that runs after an
upgrade reflects the post-upgrade state.
"""

from __future__ import annotations

from typing import Any, cast

from modules.shared.src.config.contract_config_protocol import IConfigHealthProbeProtocol
from modules.shared.src.config.taxonomy_config_vo import ConfigIssue
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate

# Block 1: Class Definition & Constructor


class ConfigHealthProbe(IConfigHealthProbeProtocol):
    """Build the functional smoke gate the update pipeline verifies against."""

    # Block 2: Protocol Method Implementation

    def build_gate(
        self,
        session: object,
        run_checks: Any,
    ) -> Any:
        """Return the callable the update pipeline runs as its postflight functional gate.

        ``session`` is the aggregate the gate checks against (an
        ``ISessionAggregate`` in production); ``run_checks`` is the check
        runner injected by the Root layer (the surface's
        ``run_doctor_checks``). The capability calls the runner at gate
        execution time so the post-update gate reflects the post-upgrade
        state (issue #506) without importing the Surface.

        Yields the non-interactive diagnostic checks as ``(name, passed,
        detail)`` triples, composed from the same check function the
        operator's ``doctor`` report uses, so the gate and the report share
        one source of truth.

        Pass the aggregate, e.g. ``session_manager.load_pool()`` or a
        production ``ISessionAggregate`` — there is no default, so a wiring
        gap cannot masquerade as an empty pool.
        """
        aggregate = cast("ISessionAggregate", session)
        runner = run_checks

        def _gate() -> tuple[tuple[str, bool, str], ...]:
            checks: list[dict[str, Any]] = runner(session=aggregate)
            return tuple((str(check["name"]), bool(check["passed"]), str(check["detail"])) for check in checks)

        return _gate

    # Block 3: Dunder Methods, Factories & Helpers

    @staticmethod
    def _check_to_issue(check: dict[str, Any]) -> ConfigIssue:
        """Convert one doctor check record into a displayable ``ConfigIssue``.

        The capability reports gate findings through the same config-domain
        value object the validator uses, so a diagnostic that surfaces a
        failing gate check and a failing config finding read the same way.
        """
        if not check.get("passed"):
            return ConfigIssue(
                field=str(check["name"]),
                message=str(check["detail"]),
                severity="error",
                category="other",
            )
        if check.get("severity") == "warning":
            return ConfigIssue(
                field=str(check["name"]),
                message=str(check["detail"]),
                severity="warning",
                category="other",
            )
        return ConfigIssue(
            field=str(check["name"]),
            message=str(check["detail"]),
            severity="error",
            category="other",
        )


__all__ = [
    "ConfigHealthProbe",
]
