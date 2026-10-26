# BACKLOG — Swarm Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/swarm/tests/ -v` at commit `00124e4`, on 2026-10-25.
- In Progress: None.
- Next Action: None; `FR-SWARM-001`, `FR-SWARM-002`, `FR-SWARM-003`, and `FR-SWARM-004` are all Done.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Evidence | Updated | FRD Ref |
|---|---:|---|---|---|---|---|---|
| FR-SWARM-001 | P1 | Done | None | — | `00124e4`: `uv run python -m pytest modules/swarm/tests/acceptance_swarm_concurrency_clamp.py -v` — 2 passed. | 2026-10-25 | FR-SWARM-001 |
| FR-SWARM-002 | P1 | Done | `MCP-01` | — | `00124e4`: `uv run python -m pytest modules/swarm/tests/unit_swarm_progress_envelope.py -v` — 11 passed. | 2026-10-25 | FR-SWARM-002, FR-SWARM-003 |
| FR-SWARM-003 | P2 | Done | `BROWSER-03` | — | `00124e4`: `uv run python -m pytest modules/swarm/tests/unit_swarm_session_shortfall.py -v` — 9 passed. | 2026-10-25 | FR-SWARM-001, FR-SWARM-004 |
| FR-SWARM-004 | P2 | Done | `BROWSER-03` | — | `00124e4`: cancel stops the running legs and the shortfall report is pinned in `unit_agent_swarm_orchestrator.py`. | 2026-10-25 | FR-SWARM-004 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A fan-out starts and reports per-leg progress | Automated | `modules/swarm/tests/unit_agent_swarm_orchestrator.py` | start and snapshot | 2026-10-05 |
| A cancel stops the running legs | Automated | `modules/swarm/tests/unit_agent_swarm_orchestrator.py` | cancel | 2026-10-05 |
| A rate-limited session does not stop the other legs | Automated | `modules/swarm/tests/unit_agent_swarm_orchestrator.py` | leg isolation | 2026-10-05 |
| A browser count above the ceiling clamps and reports | Automated | `modules/swarm/tests/acceptance_swarm_concurrency_clamp.py` | clamp and report | 2026-10-25 |

## Blockers

None.

## Dependencies

- `MCP-01` owns the progress envelope a fan-out poller consumes.
- `BROWSER-03` owns the per-leg session availability this feature clamps against.
- `FR-JOBS-002` owns the backpressure a clamped fan-out can still hit.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/swarm/tests/ -v` passes at `00124e4`, on 2026-10-25. |
| Scenario evidence | Done | All 4 scenarios mapped; the clamp-and-report scenario landed in `SWARM-01`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-24 | Added FRD Ref column mapping backlog rows to FR IDs. | @qwen-web-arwaky |
| 2026-10-25 | Advanced `SWARM-01`, `SWARM-02`, `SWARM-03` to Done with clamp, progress-envelope, and shortfall evidence at `00124e4` (#761, #762, #763). | @qwen-web-arwaky |
