# BACKLOG — Session Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/session/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: `FR-SESSION-001` and `FR-SESSION-002` — acceptance tests landing in this pass.
- Next Action: `FR-SESSION-003`, the session-directory permission repair spec — implemented (see Done row above).

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| FR-SESSION-001 | P0 | Done | `SHARED-01` | Acceptance test proving a backup write failure refuses the deletion and leaves the master profile in place — landed in `modules/session/tests/unit_capabilities_session_manager.py`. Evidence: `uv run python -m pytest modules/session/tests/unit_capabilities_session_manager.py -v` → 24 passed (2026-10-25, commit e4f5341). | 2026-10-25 | FR-SESSION-001, FR-SESSION-003 |
| FR-SESSION-002 | P1 | Done | None | Rotation returns an explicit `no_eligible_session` outcome when no eligible session remains; FR-SESSION-002 and docs/MULTI_ACCOUNT_ROTATION.md record the decision (2026-10-18, Raka). Evidence: `uv run python -m pytest modules/session/tests/ -v` → 24 passed (2026-10-25, commit 03d72dc). | 2026-10-25 | FR-SESSION-002, FR-SESSION-004 |
| FR-SESSION-003 | P2 | Done | `BROWSER-03` | Cross-user session-directory permission repair implemented in `SessionManager.repair_session_dir_permissions`, wired into `_ensure_dirs` so a cross-user-owned dir is repaired in place when writable or refused with reason `session_dir_cross_user` before any browser process starts. Evidence: `uv run python -m pytest modules/session/tests/ -v` → 147 passed (this commit). FR-SESSION-004 carries to Done. | 2026-10-25 | FR-SESSION-004 |
| FR-SESSION-004 | P0 | Done | None | The rotator selects the next healthy session, skipping already-tried and rate-limited ones; an exhausted pool returns the reasoned `no_eligible_session` outcome with `empty_pool` / `all_sessions_limited` and a recovery action. | 2026-10-25 | FR-SESSION-004 |
| FR-SESSION-005 | P1 | Done | None | A stale auth session is renewed transparently via the refresh-token flow; renewal failure raises `AuthRequiredError` so the caller falls back to manual login. | 2026-10-25 | FR-SESSION-005 |
| FR-SESSION-006 | P1 | Done | None | The profile preparer owns the mode→clone decision: login mode yields the master path, every other mode yields an ephemeral clone so concurrent browser processes never hit a SingletonLock conflict. | 2026-10-25 | FR-SESSION-006 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A cancel on a run with no active pipeline is a no-op | Automated | `modules/session/tests/unit_agent_cancel_isolation.py` | cancel isolation | 2026-10-05 |
| The session aggregate reports its verdict from the browser seam | Automated | `modules/session/tests/unit_agent_session_orchestrator.py` | session aggregate | 2026-10-05 |
| Rotation skips a rate-limited session | Automated | `modules/session/tests/unit_agent_session_orchestrator.py` | rotation | 2026-10-05 |
| A backup write failure refuses the deletion | Automated | `modules/session/tests/unit_capabilities_session_manager.py` | backup failure refuses deletion | 2026-10-18 |
| Every pooled session rate limited reports the throttle | Automated | `modules/session/tests/unit_capabilities_session_rotator.py` | rotation exhaustion | 2026-10-18 |

## Blockers

None.

## Dependencies

- `SHARED-01` owns the session-backup utility this feature refuses to delete without.
- `BROWSER-03` owns the profile-permission repair the launch path performs.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/session/tests/ -v` passes. |
| Scenario evidence | Done | 5 of 5 scenarios mapped; the `FR-SESSION-001` gap closed by the backup-guard tests in `unit_capabilities_session_manager.py`. |
| Docs | Done | [FRD.md](FRD.md) reconciled with the eight implemented verbs and the ratified code behavior. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-18 | `FR-SESSION-001`/`FR-SESSION-002` tests landed; FRD reconciled with the eight implemented verbs (aggregate API table, FR-SESSION-001/002/004). | @qwen-web-arwaky |
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-25 | ROADMAP roll-up advanced to Done; FR-orphan refs added: FR-SESSION-001 to FR-SESSION-001 row, FR-SESSION-002 to FR-SESSION-002 row; row IDs renumbered to the FRD FR-IDs and FR-SESSION-003/004/005/006 rows added. | @qwen-web-arwaky |
| 2026-10-25 | Evidence cells completed for FR-SESSION-001/002 (three-proof rule: command + pass-result + commit SHA). | @qwen-web-arwaky |
| 2026-10-24 | Added FRD Ref column mapping backlog rows to FR IDs. | @qwen-web-arwaky |
