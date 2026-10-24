# BACKLOG — Update Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/update/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05; `UPDATE-01` acceptance scenario added on 2026-10-24.
- In Progress: None.
- Next Action: `UPDATE-02`.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|
| UPDATE-01 | P0 | Done | None | None — acceptance scenario proving a failed health gate restores the install before the browser build added to `acceptance_update_rollback_ordering.py`. | 2026-10-24 |
| UPDATE-02 | P1 | Ready | None | Define the rollback acceptance criteria the surface reports on, and re-validate the six open findings against the current contract. | 2026-10-05 |
| UPDATE-03 | P2 | Ready | None | Add an acceptance scenario proving a postflight failure routes through the same rollback path a health-gate failure uses. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A rollback restores the previous release | Automated | `modules/update/tests/unit_update_manager_rollback.py` | rollback | 2026-10-05 |
| An upgrade runs its steps under a subprocess boundary | Automated | `modules/update/tests/unit_update_manager_subprocess.py` | subprocess steps | 2026-10-05 |
| The aggregate routes each verb | Automated | `modules/update/tests/unit_agent_update_orchestrator.py` | verb routing | 2026-10-05 |
| Rollback steps run in reverse install order | Automated | `modules/update/tests/acceptance_update_rollback_ordering.py` | `test_acceptance_a_failed_health_gate_restores_the_install_before_the_browser` | 2026-10-24 |

## Blockers

None.

## Dependencies

- `CLI-02` owns the update surface's report of this feature's rollback outcome.
- `BROWSER-01` owns the managed-build trust rule the browser sync installs under.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/update/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | All 4 scenarios mapped; the former `UPDATE-01` gap closed on 2026-10-24. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-24 | Advance UPDATE-01 to Done with rollback-ordering acceptance scenario. | @qwen-web-arwaky |
