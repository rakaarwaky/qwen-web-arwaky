# BACKLOG — Session Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/session/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: `SESSION-01` and `SESSION-02` — acceptance tests landing in this pass.
- Next Action: `SESSION-03`, the session-directory permission repair spec.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| SESSION-01 | P0 | Done | `SHARED-01` | Acceptance test proving a backup write failure refuses the deletion and leaves the master profile in place — landed in `modules/session/tests/unit_capabilities_session_manager.py`. | 2026-10-18 | FR-SESSION-001, FR-SESSION-003 |
| SESSION-02 | P1 | Done | None | Rotation returns an explicit `no_eligible_session` outcome when no eligible session remains; FR-SESSION-002 and docs/MULTI_ACCOUNT_ROTATION.md record the decision (2026-10-18, Raka). | 2026-10-18 | FR-SESSION-002, FR-SESSION-004 |
| SESSION-03 | P2 | Ready | `BROWSER-03` | Specify the session-directory permission repair when the browser launches the context under a different user. | 2026-10-05 | FR-SESSION-004 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A cancel on a run with no active pipeline is a no-op | Automated | `modules/session/tests/unit_agent_cancel_isolation.py` | cancel isolation | 2026-10-05 |
| The session aggregate reports its verdict from the browser seam | Automated | `modules/session/tests/unit_agent_session_orchestrator.py` | session aggregate | 2026-10-05 |
| Rotation skips a rate-limited session | Automated | `modules/session/tests/unit_agent_session_orchestrator.py` | rotation | 2026-10-05 |
| A backup write failure refuses the deletion | Automated | `modules/session/tests/unit_capabilities_session_manager.py` | backup failure refuses deletion | 2026-10-18 |
| Every pooled session rate limited reports the throttle | Automated | `modules/session/tests/unit_capabilities_session_rotation_adapter.py` | rotation exhaustion | 2026-10-18 |

## Blockers

None.

## Dependencies

- `SHARED-01` owns the session-backup utility this feature refuses to delete without.
- `BROWSER-03` owns the profile-permission repair the launch path performs.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/session/tests/ -v` passes. |
| Scenario evidence | Done | 5 of 5 scenarios mapped; the `SESSION-01` gap closed by the backup-guard tests in `unit_capabilities_session_manager.py`. |
| Docs | Done | [FRD.md](FRD.md) reconciled with the eight implemented verbs and the ratified code behavior. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-18 | `SESSION-01`/`SESSION-02` tests landed; FRD reconciled with the eight implemented verbs (aggregate API table, FR-SESSION-001/002/004). | @qwen-web-arwaky |
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-25 | ROADMAP roll-up advanced to Done; FR-orphan refs added: FR-SESSION-001 to SESSION-01, FR-SESSION-002 to SESSION-02. | @qwen-web-arwaky |
| 2026-10-24 | Added FRD Ref column mapping backlog rows to FR IDs. | @qwen-web-arwaky |
