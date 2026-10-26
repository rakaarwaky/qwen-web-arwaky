# BACKLOG — Browser Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/browser/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05; `BROWSER-01` binary-trust acceptance test added at `modules/browser/tests/acceptance_browser_binary_trust.py`, on 2026-10-24.
- In Progress: None.
- Next Action: None.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| FR-BROWSER-003 | P0 | Done | None | Add an acceptance scenario proving a PATH-discovered browser binary that fails the ownership check is refused even when no managed build is present. Evidence: `uv run python -m pytest modules/browser/tests/acceptance_browser_binary_trust.py -v` → 2 passed (2026-10-25, commit `fa5ba41`). | 2026-10-25 | FR-BROWSER-001 |
| FR-BROWSER-004 | P1 | Done | None | None — the pinned DOM fixture and `unit_navigation_selector_regression.py` fail the browser suite on selector drift. Evidence: `uv run python -m pytest modules/browser/tests/unit_navigation_selector_regression.py -v` → 8 passed (2026-10-25, commit `d76437b`). | 2026-10-25 | FR-BROWSER-002 |
| FR-BROWSER-005 | P2 | Done | `SESSION-01` | None — cross-user ownership detection, in-place repair, refusal escalation, and safety constraints are specified in FRD.md under FR-BROWSER-001 Business Rules (BROWSER-03). Evidence: `uv run python -m pytest modules/browser/tests/ -v` → 87 passed (2026-10-25, commit `668daae` + `75748ff`). | 2026-10-25 | FR-BROWSER-001, FR-BROWSER-002 |
| FR-BROWSER-006 | P2 | Done | FR-BROWSER-004 | None — per-context and per-page diagnostics (asset-abort route, page-creation hook, per-page request/console/response listeners, URL scrubbing, third-party noise demotion to DEBUG) are wired by `wire_diagnostics` on the live context and verified by the browser suite. Evidence: `uv run python -m pytest modules/browser/tests/ -v` → 87 passed (2026-10-25, commit `668daae` + `75748ff`). | 2026-10-25 | FR-BROWSER-006 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A launch yields an authenticated page and tears down on caller exception | Automated | `modules/browser/tests/unit_agent_browser_orchestrator.py` | open session teardown | 2026-10-05 |
| A login-redirected page raises an authentication error | Automated | `modules/browser/tests/unit_browser_adapter.py` | check auth | 2026-10-05 |
| A non-owner-only session directory is repaired to `0700` | Automated | `modules/browser/tests/unit_browser_adapter.py` | session dir permissions | 2026-10-05 |
| A PATH-discovered binary that fails the ownership check is refused | Automated | `modules/browser/tests/acceptance_browser_binary_trust.py` | test_acceptance_path_binary_with_foreign_owner_is_refused_without_managed_build / test_acceptance_no_trusted_binary_raises_browser_launch_error | 2026-10-24 |
| A navigation retry path whose DOM selector drifts is caught by the browser suite | Automated | `modules/browser/tests/unit_navigation_selector_regression.py` | pinned navigation selectors | 2026-10-24 |
| A cross-user-owned session directory is repaired in place or refused before launch | Specified | [FRD.md FR-BROWSER-001 Business Rules](FRD.md) | BROWSER-03 | 2026-10-24 |

## Blockers

None.

## Dependencies

- `SESSION-01` owns the session pool this feature's context launches over.
- `PROMPT-01` owns the retry budget the navigation path reuses.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/browser/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 6 of 6 scenarios mapped. |
| Docs | Done | [FRD.md](FRD.md) is specification-only; `BROWSER-03` cross-user repair is specified in FR-BROWSER-001. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-24 | Added FRD Ref column mapping backlog rows to FR IDs. | @qwen-web-arwaky |
| 2026-10-24 | BROWSER-03 specified in FRD.md under FR-BROWSER-001; row advanced to Done. | @qwen-web-arwaky |
| 2026-10-25 | Evidence cells completed (three-proof rule). | @qwen-web-arwaky |
