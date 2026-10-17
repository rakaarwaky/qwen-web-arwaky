"""CLI surface: observability command — query run metrics and quality reports.

Smart surface: maps parsed args to the IObservabilityAggregate verbs
(write_quality_report, metrics_snapshot) and formats the response as a
human-readable summary or JSON envelope.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from modules.shared.src.logging.contract_logging_aggregate import IObservabilityAggregate
from modules.shared.src.logging.taxonomy_logging_vo import (
    MetricsSnapshot,
    ObservabilityRequest,
)


def _cmd_report(args: argparse.Namespace, orchestrator: IObservabilityAggregate) -> int:
    """Write and display the quality report for the last run."""
    json_output = bool(getattr(args, "json", False))
    response = orchestrator.execute(ObservabilityRequest(verb="write_quality_report"))
    if not response.success:
        print(f"[ERROR] {response.error}", file=sys.stderr)
        return 1

    report_path = response.report_path
    if json_output:
        payload: dict[str, Any] = {"success": True, "report_path": str(report_path)}
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"✅ Quality report written: {report_path}")
    return 0


def _cmd_status(args: argparse.Namespace, orchestrator: IObservabilityAggregate) -> int:
    """Show the metrics snapshot for the last run."""
    json_output = bool(getattr(args, "json", False))
    response = orchestrator.execute(ObservabilityRequest(verb="metrics_snapshot"))
    if not response.success:
        print(f"[ERROR] {response.error}", file=sys.stderr)
        return 1

    snapshot: MetricsSnapshot | None = response.metrics
    if snapshot is None:
        print("No metrics snapshot available.")
        return 0

    if json_output:
        print(
            json.dumps(
                {
                    "success": True,
                    "counters": dict(snapshot.counters),
                    "total_executions": snapshot.total_executions,
                    "successful_executions": snapshot.successful_executions,
                    "success_rate": snapshot.success_rate,
                },
                indent=2,
                default=str,
            )
        )
    else:
        print("📈 Metrics snapshot:")
        print(
            f"   total={snapshot.total_executions} "
            f"successful={snapshot.successful_executions} "
            f"rate={snapshot.success_rate}"
        )
    return 0


def handle_observability_command(
    args: argparse.Namespace,
    orchestrator: IObservabilityAggregate,
) -> int:
    """Handle observability subcommand via the IObservabilityAggregate verbs."""
    command = getattr(args, "command", None)

    if command == "report":
        return _cmd_report(args, orchestrator)
    if command == "status":
        return _cmd_status(args, orchestrator)

    print("Use 'qwen-web-arwaky observability --help' for usage")
    return 1


__all__ = ["handle_observability_command"]
