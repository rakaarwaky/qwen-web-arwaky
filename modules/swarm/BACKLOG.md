# BACKLOG — Swarm Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/swarm/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Blocked: None.
- Next Action: `SWARM-01`, the clamp-reporting acceptance gap.

## Backlog

| ID | Priority | State | Health | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|---|
| SWARM-01 | P1 | Ready | On Track | None | Add an acceptance scenario proving a browser count above the ceiling clamps and reports the clamp. | 2026-10-05 |
| SWARM-02 | P1 | Ready | On Track | `MCP-01` | Specify the fan-out progress envelope a poller can rely on. | 2026-10-05 |
| SWARM-03 | P2 | Ready | On Track | `BROWSER-03` | Specify behavior when the session pool offers fewer healthy sessions than the clamped browser count. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A fan-out starts and reports per-leg progress | Automated | `modules/swarm/tests/unit_agent_swarm_orchestrator.py` | start and snapshot | 2026-10-05 |
| A cancel stops the running legs | Automated | `modules/swarm/tests/unit_agent_swarm_orchestrator.py` | cancel | 2026-10-05 |
| A rate-limited session does not stop the other legs | Automated | `modules/swarm/tests/unit_agent_swarm_orchestrator.py` | leg isolation | 2026-10-05 |
| A browser count above the ceiling clamps and reports | Gap | none yet | see `SWARM-01` | 2026-10-05 |

## Blockers

None.

## Dependencies

- `MCP-01` owns the progress envelope a fan-out poller consumes.
- `BROWSER-03` owns the per-leg session availability this feature clamps against.
- `JOBS-02` owns the backpressure a clamped fan-out can still hit.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/swarm/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 3 of 4 scenarios mapped; one gap tracked as `SWARM-01`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

- Per-leg prompt variation and heterogeneous leg configuration stay out of scope.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
