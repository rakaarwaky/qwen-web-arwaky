"""Swarm MVP taxonomy value objects and snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, NewType

SwarmId = NewType("SwarmId", str)
SwarmStatus = Literal["queued", "running", "completed", "partial", "failed", "cancelled"]
AgentStatus = Literal["queued", "running", "retrying", "completed", "failed", "cancelled"]


@dataclass(frozen=True)
class SwarmAgentSnapshot:
    """Persistable status for one adaptive template agent."""

    agent_id: str
    status: AgentStatus
    attempt: int = 0
    output_path: Path | None = None
    error: str | None = None
    duration_sec: float | None = None


@dataclass(frozen=True)
class SwarmSnapshot:
    """Persistable status for one Swarm execution."""

    swarm_id: SwarmId
    input_path: Path
    root_path: Path
    status: SwarmStatus
    max_attempts: int
    browser_concurrency: int
    agents: tuple[SwarmAgentSnapshot, ...] = field(default_factory=tuple)

    @property
    def completed_count(self) -> int:
        """Number of agents that finished successfully."""
        return sum(agent.status == "completed" for agent in self.agents)

    @property
    def failed_count(self) -> int:
        """Number of agents that ended in failure."""
        return sum(agent.status == "failed" for agent in self.agents)


__all__ = ["AgentStatus", "SwarmAgentSnapshot", "SwarmId", "SwarmSnapshot", "SwarmStatus"]
