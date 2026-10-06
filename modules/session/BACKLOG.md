# BACKLOG — Session Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/session/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Blocked: None.
- Next Action: `SESSION-01`, the backup-refusal acceptance gap.

## Backlog

| ID | Priority | State | Health | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|---|
| SESSION-01 | P0 | Ready | At Risk | `SHARED-01` | Add an acceptance scenario proving a backup write failure refuses the deletion and leaves the master profile in place. | 2026-10-05 |
| SESSION-02 | P1 | Ready | On Track | None | Specify rotation behavior when every pooled session is rate limited. | 2026-10-05 |
| SESSION-03 | P2 | Ready | On Track | `BROWSER-03` | Specify the session-directory permission repair when the browser launches the context under a different user. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A cancel on a run with no active pipeline is a no-op | Automated | `modules/session/tests/unit_agent_cancel_isolation.py` | cancel isolation | 2026-10-05 |
| The session aggregate reports its verdict from the browser seam | Automated | `modules/session/tests/unit_agent_session_orchestrator.py` | session aggregate | 2026-10-05 |
| Rotation skips a rate-limited session | Automated | `modules/session/tests/unit_agent_session_orchestrator.py` | rotation | 2026-10-05 |
| A backup write failure refuses the deletion | Gap | none yet | see `SESSION-01` | 2026-10-05 |

## Blockers

None.

## Dependencies

- `SHARED-01` owns the session-backup utility this feature refuses to delete without.
- `BROWSER-03` owns the profile-permission repair the launch path performs.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/session/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 3 of 4 scenarios mapped; one gap tracked as `SESSION-01`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

- Session pool replication across machines stays out of scope; the pool is local to the workspace.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
