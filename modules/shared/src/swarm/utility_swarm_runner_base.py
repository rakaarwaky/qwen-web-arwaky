"""Utility layer (utility_swarm_runner_base): shared fan-out helpers.

The swarm feature exposes three consumer seams — start, progress, cancel —
each sealed in its own capability file, with one shared registry behind
them. This utility holds the pure helpers those seams need — the retry
predicate, the snapshot replacements, the manifest writer — so each
capability file stays a thin class around one protocol and never re-states
another seam's logic.

It is not a protocol: it is stateless wiring the capability files import.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path

from modules.shared.src.swarm.taxonomy_swarm_vo import (
    AgentStatus,
    SwarmAgentSnapshot,
    SwarmSnapshot,
    SwarmStatus,
)

log = logging.getLogger(__name__)

#: Error text a cancelled leg reports instead of its own failure.
CANCELLED_ERROR = "Cancelled by user"


#: Failure text worth retrying. A lifecycle-gate rejection is here because
#: it means a concurrent attachment run missed its DOCUMENT_PARSED
#: predecessor on that attempt only — a fresh browser session recovers it,
#: so failing the leg immediately would report a transient race as terminal.
RETRYABLE_TOKENS: tuple[str, ...] = (
    "timeout",
    "transient",
    "rate limit",
    "503",
    "502",
    "504",
    "temporarily",
    "lifecycle gate rejected",
)


def is_retryable(message: str) -> bool:
    """Return True when *message* names a transient failure worth retrying."""
    lowered = message.casefold()
    return any(token in lowered for token in RETRYABLE_TOKENS)


def replace_status(snapshot: SwarmSnapshot, status: SwarmStatus) -> SwarmSnapshot:
    """Return a copy of *snapshot* with its status replaced."""
    return SwarmSnapshot(
        swarm_id=snapshot.swarm_id,
        input_path=snapshot.input_path,
        root_path=snapshot.root_path,
        status=status,
        max_attempts=snapshot.max_attempts,
        browser_concurrency=snapshot.browser_concurrency,
        agents=snapshot.agents,
    )


def replace_agent(snapshot: SwarmSnapshot, agent: SwarmAgentSnapshot) -> SwarmSnapshot:
    """Return a copy of *snapshot* with *agent* substituted for the leg with the same id."""
    return SwarmSnapshot(
        swarm_id=snapshot.swarm_id,
        input_path=snapshot.input_path,
        root_path=snapshot.root_path,
        status=snapshot.status,
        max_attempts=snapshot.max_attempts,
        browser_concurrency=snapshot.browser_concurrency,
        agents=tuple(agent if current.agent_id == agent.agent_id else current for current in snapshot.agents),
    )


def mark_cancelled(snapshot: SwarmSnapshot) -> SwarmSnapshot:
    """Return *snapshot* with every unfinished leg and the run marked cancelled.

    A leg that already reached a terminal state keeps it: cancelling a run
    must not rewrite the outcome of work that actually finished.
    """
    cancelled = replace_status(snapshot, "cancelled")
    return SwarmSnapshot(
        swarm_id=cancelled.swarm_id,
        input_path=cancelled.input_path,
        root_path=cancelled.root_path,
        status=cancelled.status,
        max_attempts=cancelled.max_attempts,
        browser_concurrency=cancelled.browser_concurrency,
        agents=tuple(
            agent
            if agent.status in {"completed", "failed"}
            else SwarmAgentSnapshot(
                agent_id=agent.agent_id,
                status="cancelled",
                attempt=agent.attempt,
                output_path=agent.output_path,
                error=CANCELLED_ERROR,
                duration_sec=agent.duration_sec,
            )
            for agent in cancelled.agents
        ),
    )


def mark_agent_progress(
    snapshot: SwarmSnapshot,
    role: str,
    status: AgentStatus,
    attempt: int,
    output_path: Path,
    error: str | None,
    duration_sec: float | None,
) -> SwarmSnapshot:
    """Return *snapshot* with one leg's status replaced and the run status settled.

    A run that has been cancelled keeps its cancelled status: a leg that
    was already in flight when the cancel landed must not flip the run back
    to running or partial. A run whose legs have all reached a terminal
    state settles to ``completed`` when every leg succeeded and ``partial``
    otherwise; a run with legs still working stays as it is.
    """
    updated = replace_agent(
        snapshot,
        SwarmAgentSnapshot(
            agent_id=role,
            status=status,
            attempt=attempt,
            output_path=output_path,
            error=error,
            duration_sec=duration_sec,
        ),
    )
    if snapshot.status == "cancelled":
        return updated
    if all(agent.status in {"completed", "failed", "cancelled"} for agent in updated.agents):
        settled: SwarmStatus = (
            "completed" if all(agent.status == "completed" for agent in updated.agents) else "partial"
        )
        return replace_status(updated, settled)
    return updated


def write_manifest(snapshot: SwarmSnapshot) -> None:
    """Persist the snapshot as JSON next to the swarm output root."""
    manifest = snapshot.root_path / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "swarm_id": snapshot.swarm_id,
                "input_path": str(snapshot.input_path),
                "root_path": str(snapshot.root_path),
                "status": snapshot.status,
                "max_attempts": snapshot.max_attempts,
                "browser_concurrency": snapshot.browser_concurrency,
                "agents": [
                    {
                        "agent_id": agent.agent_id,
                        "status": agent.status,
                        "attempt": agent.attempt,
                        "output_path": str(agent.output_path),
                        "error": agent.error,
                        "duration_sec": agent.duration_sec,
                    }
                    for agent in snapshot.agents
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def new_swarm_id() -> str:
    """Generate a short, URL-safe swarm identifier."""
    return f"swarm-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"


__all__ = [
    "CANCELLED_ERROR",
    "RETRYABLE_TOKENS",
    "is_retryable",
    "mark_agent_progress",
    "mark_cancelled",
    "new_swarm_id",
    "replace_agent",
    "replace_status",
    "write_manifest",
]
