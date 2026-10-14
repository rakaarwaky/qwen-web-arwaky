"""Utility layer (utility_swarm_runner_base): shared fan-out engine helpers.

The swarm runner owns one fan-out engine but exposes three capability
seams — start, progress, cancel — each sealed in its own protocol file.
This utility holds the pure, stateless helpers that every seam needs —
the retry predicate, the snapshot-status replacement, the manifest
writer — so each capability file stays a thin class around one protocol
and never re-states another seam's logic.

It is not a protocol: it is stateless wiring the capability files import.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path

from modules.shared.src.swarm.taxonomy_swarm_vo import SwarmSnapshot, SwarmStatus

log = logging.getLogger(__name__)


def is_retryable(message: str) -> bool:
    """Return True when *message* names a transient failure worth retrying."""
    lowered = message.casefold()
    return any(token in lowered for token in ("timeout", "transient", "rate limit", "503", "502", "504", "temporarily"))


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


__all__ = ["is_retryable", "replace_status", "write_manifest", "new_swarm_id"]