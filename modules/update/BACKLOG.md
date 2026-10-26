# BACKLOG — Update Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/update/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05; `UPDATE-01` acceptance scenario added on 2026-10-24.
- In Progress: None.
- Next Action: None.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| FR-UPDATE-001 | P0 | Done | None | Acceptance scenario proving a failed health gate restores the install before the browser build added to `acceptance_update_rollback_ordering.py`. Evidence: `uv run python -m pytest modules/update/tests/acceptance_update_rollback_ordering.py -v` → 4 passed (2026-10-25, commit fa89616). | 2026-10-25 | FR-UPDATE-001, FR-UPDATE-004 |
| FR-UPDATE-002 | P1 | Done | None | Rollback acceptance criteria defined in FRD.md matching surface report contract; six cross-cutting findings (#299, #355, #329, #340, #325, #289/#349) revalidated against current contract. Evidence: `uv run python -m pytest modules/update/tests/ -v` → 35 passed (2026-10-25, commits 4c98863 and fd55857). | 2026-10-25 | FR-UPDATE-002, FR-UPDATE-003, FR-UPDATE-004 |
| FR-UPDATE-003 | P2 | Done | None | Acceptance scenario proving a postflight failure routes through the same rollback path a health-gate failure uses; landed in `modules/update/tests/acceptance_update_postflight_rollback.py`. Evidence: `uv run python -m pytest modules/update/tests/acceptance_update_postflight_rollback.py -v` → 2 passed (2026-10-25, commit fd55857). | 2026-10-25 | FR-UPDATE-003, FR-UPDATE-004 |
| FR-UPDATE-004 | P2 | Done | None | Rollback ordering pinned: a failed health gate restores the install before the browser build; covered by `acceptance_update_rollback_ordering.py` and `unit_update_manager_rollback.py`. Evidence: `uv run python -m pytest modules/update/tests/acceptance_update_rollback_ordering.py modules/update/tests/unit_update_manager_rollback.py -v` → passes (2026-10-25, commit fa89616). | 2026-10-25 | FR-UPDATE-004 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A rollback restores the previous release | Automated | `modules/update/tests/unit_update_manager_rollback.py` | rollback | 2026-10-05 |
| An upgrade runs its steps under a subprocess boundary | Automated | `modules/update/tests/unit_update_manager_subprocess.py` | subprocess steps | 2026-10-05 |
| The aggregate routes each verb | Automated | `modules/update/tests/unit_agent_update_orchestrator.py` | verb routing | 2026-10-05 |
| Rollback steps run in reverse install order | Automated | `modules/update/tests/acceptance_update_rollback_ordering.py` | `test_acceptance_a_failed_health_gate_restores_the_install_before_the_browser` | 2026-10-24 |
| A postflight failure routes through the same rollback path a health-gate failure uses | Automated | `modules/update/tests/acceptance_update_postflight_rollback.py` | postflight failure rollback | 2026-10-24 |

## Blockers

None.

## Dependencies

- `CLI-02` owns the update surface's report of this feature's rollback outcome.
- `BROWSER-01` owns the managed-build trust rule the browser sync installs under.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/update/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | All 5 scenarios mapped. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-24 | Advance UPDATE-01 to Done with rollback-ordering acceptance scenario. | @qwen-web-arwaky |
| 2026-10-24 | UPDATE-02 advanced to Done: rollback acceptance criteria defined in FRD.md; six cross-cutting findings revalidated against the current contract. | @qwen-web-arwaky |
| 2026-10-25 | Added FRD Ref column to header + separator + all 3 rows: UPDATE-01 -> FR-UPDATE-001/004, UPDATE-02 -> FR-UPDATE-002/003/004, UPDATE-03 -> FR-UPDATE-003/004. | @qwen-web-arwaky |
| 2026-10-25 | Evidence cells completed for UPDATE-01/02/03 (three-proof rule: command + pass-result + commit SHA). | @qwen-web-arwaky |
| 2026-10-24 | UPDATE-03 advanced to Done: postflight-failure rollback acceptance test added in `modules/update/tests/acceptance_update_postflight_rollback.py`. | @qwen-web-arwaky |
