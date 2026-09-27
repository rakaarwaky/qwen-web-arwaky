"""Capabilities: host capacity advising (AES403).

Implements ``IConfigCapacityProtocol``.

Reports the browser fan-out this host can carry and where the effective
worker count came from. The doctor derived this inline and the container
read ``QWEN_WEB_MAX_WORKERS`` itself, so the number a diagnostic showed and
the number the executor used were two separate derivations of the same
question (issue #291).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from modules.shared.src.contract_config_protocol import IConfigCapacityProtocol
from modules.shared.src.taxonomy_config_vo import ByteCount, CapacityReport, WorkerCount
from modules.shared.src.utility_core_capacity import (
    available_memory_bytes,
    format_bytes,
    recommended_max_workers,
    total_memory_bytes,
)
from modules.shared.src.utility_core_env import QWEN_WEB_MAX_WORKERS

#: Names the effective worker count can come from, for the report's ``source``.
SOURCE_DERIVED = "derived from measured available memory"
SOURCE_OVERRIDE = f"{QWEN_WEB_MAX_WORKERS} environment override"


class ConfigCapacityAdvisor(IConfigCapacityProtocol):
    """Report measured host capacity against the configured worker count."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        """Bind the environment source the advisor reads the override from.

        *env* defaults to the process environment; a test supplies a mapping
        so the override path is reachable without mutating the real one.
        """
        self._env: Mapping[str, str] = env if env is not None else os.environ

    def report(self) -> CapacityReport:
        """Return measured capacity, the recommended limit, and the effective one.

        ``over_capacity`` marks the case an operator most needs to see: an
        env override raised the effective count above what the measured
        memory supports, which fans out browsers the host cannot hold.
        """
        total = ByteCount(total_memory_bytes() or 0)
        available = ByteCount(available_memory_bytes() or 0)
        recommended = WorkerCount(recommended_max_workers())
        override = self._override()
        effective = WorkerCount(override) if override is not None else recommended
        return CapacityReport(
            total_memory=total,
            available_memory=available,
            recommended_max_workers=recommended,
            effective_max_workers=effective,
            source=SOURCE_OVERRIDE if override is not None else SOURCE_DERIVED,
            over_capacity=override is not None and override > recommended,
        )

    def summary(self) -> str:
        """Return the one-line operator description this report is built from."""
        report = self.report()
        available = report.available_memory or report.total_memory
        measured = format_bytes(available) if available else "unknown memory"
        return (
            f"{format_bytes(report.total_memory) if report.total_memory else 'unknown'} total / "
            f"{measured} available; recommended max workers {report.recommended_max_workers}, "
            f"effective {report.effective_max_workers} ({report.source})"
        )

    def _override(self) -> int | None:
        """Return the configured worker count, or None when unset or unusable.

        An unparseable value falls back to the derived limit so a typo in the
        operator's environment cannot silently zero the executor.
        """
        raw = self._env.get(QWEN_WEB_MAX_WORKERS, "").strip()
        if not raw.isdigit():
            return None
        value = int(raw)
        return value if value > 0 else None


__all__ = [
    "SOURCE_DERIVED",
    "SOURCE_OVERRIDE",
    "ConfigCapacityAdvisor",
]
