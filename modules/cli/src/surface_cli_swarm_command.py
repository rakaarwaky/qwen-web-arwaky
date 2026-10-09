"""CLI surface: swarm command — run and manage a multi-agent Swarm fan-out.

Smart surface: maps parsed args to the ISwarmAggregate verbs
(start, snapshot, cancel) and formats the SwarmSnapshot as a human-readable
report or JSON envelope. The Swarm orchestrator owns the resource-governance
warning (issue #277); this surface surfaces it to the operator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from modules.shared.src.contract_swarm_aggregate import ISwarmAggregate
from modules.shared.src.taxonomy_swarm_vo import SwarmRequest, SwarmSnapshot


def _render_snapshot(snapshot: SwarmSnapshot) -> None:
    """Print a compact Swarm progress report to the terminal."""
    status = snapshot.status
    completed = snapshot.completed_count
    failed = snapshot.failed_count
    total = len(snapshot.agents)
    print(f"⌬ Swarm {snapshot.swarm_id} — {status.upper()}")
    print(f"   Input:      {snapshot.input_path}")
    print(f"   Output:     {snapshot.root_path}")
    print(f"   Concurrency: {snapshot.browser_concurrency} browsers · max {snapshot.max_attempts} attempts/leg")
    print(f"   Progress:   {completed}/{total} completed · {failed} failed")
    if snapshot.agents:
        print("   Agents:")
        for agent in snapshot.agents:
            icon = "✓" if agent.status == "completed" else ("✗" if agent.status == "failed" else "⋯")
            extra = f" · {agent.error}" if agent.error else ""
            print(f"     {icon} {agent.agent_id:<24} {agent.status:<10} attempt {agent.attempt}{extra}")


def _cmd_start(args: argparse.Namespace, swarm: ISwarmAggregate) -> int:
    """Start a Swarm fan-out over every discovered role template."""
    input_path = Path(args.input).expanduser().resolve()
    json_output = bool(getattr(args, "json", False))

    if not input_path.exists():
        print(f"[ERROR] Swarm input not found: {input_path}", file=sys.stderr)
        return 1

    response = swarm.execute(SwarmRequest(verb="start", input_path=input_path))
    if response.error:
        print(f"[ERROR] {response.error}", file=sys.stderr)
        return 1
    snapshot = response.snapshot
    assert snapshot is not None

    if json_output:
        print(
            json.dumps(
                {
                    "success": True,
                    "swarm_id": snapshot.swarm_id,
                    "status": snapshot.status,
                    "input_path": str(snapshot.input_path),
                    "root_path": str(snapshot.root_path),
                    "browser_concurrency": snapshot.browser_concurrency,
                    "completed_count": snapshot.completed_count,
                    "failed_count": snapshot.failed_count,
                    "agents": [
                        {"agent_id": a.agent_id, "status": a.status, "attempt": a.attempt, "error": a.error}
                        for a in snapshot.agents
                    ],
                },
                indent=2,
                default=str,
            )
        )
    else:
        _render_snapshot(snapshot)
        print(f"\n✅ Swarm started. Poll with: qwen-web-arwaky swarm status {snapshot.swarm_id}")
    return 0


def _cmd_status(args: argparse.Namespace, swarm: ISwarmAggregate) -> int:
    """Report the current state of a Swarm by ID."""
    swarm_id = args.swarm_id
    if len(swarm_id) > 128 or any(c in swarm_id for c in "/\\\0"):
        print(f"[ERROR] Invalid swarm ID: {swarm_id!r}", file=sys.stderr)
        return 1
    json_output = bool(getattr(args, "json", False))
    response = swarm.execute(SwarmRequest(verb="snapshot", swarm_id=swarm_id))
    if response.error:
        print(f"[ERROR] {response.error}", file=sys.stderr)
        return 1
    snapshot = response.snapshot
    if snapshot is None:
        print(f"[ERROR] No Swarm found with ID: {swarm_id}", file=sys.stderr)
        return 1

    if json_output:
        print(
            json.dumps(
                {
                    "success": True,
                    "swarm_id": snapshot.swarm_id,
                    "status": snapshot.status,
                    "completed_count": snapshot.completed_count,
                    "failed_count": snapshot.failed_count,
                    "agents": [
                        {"agent_id": a.agent_id, "status": a.status, "attempt": a.attempt, "error": a.error}
                        for a in snapshot.agents
                    ],
                },
                indent=2,
                default=str,
            )
        )
    else:
        _render_snapshot(snapshot)
    return 0


def _cmd_cancel(args: argparse.Namespace, swarm: ISwarmAggregate) -> int:
    """Cancel a running Swarm by ID."""
    swarm_id = args.swarm_id
    if len(swarm_id) > 128 or any(c in swarm_id for c in "/\\\0"):
        print(f"[ERROR] Invalid swarm ID: {swarm_id!r}", file=sys.stderr)
        return 1
    json_output = bool(getattr(args, "json", False))
    response = swarm.execute(SwarmRequest(verb="cancel", swarm_id=swarm_id))
    if response.error:
        print(f"[ERROR] {response.error}", file=sys.stderr)
        return 1
    snapshot = response.snapshot
    if json_output:
        print(
            json.dumps(
                {"success": True, "swarm_id": swarm_id, "status": snapshot.status if snapshot else "cancelled"},
                indent=2,
            )
        )
    else:
        status = snapshot.status if snapshot else "cancelled"
        print(f"✅ Swarm {swarm_id} cancelled (status: {status}).")
    return 0


def handle(args: argparse.Namespace, swarm: ISwarmAggregate) -> int:
    """Dispatch the swarm subcommand to the matching handler."""
    verb = getattr(args, "swarm_command", None)
    if verb == "start":
        return _cmd_start(args, swarm)
    if verb == "status":
        return _cmd_status(args, swarm)
    if verb == "cancel":
        return _cmd_cancel(args, swarm)
    print("Use 'qwen-web-arwaky swarm --help' for usage")
    return 1


__all__ = ["handle"]
