# BACKLOG — Browser Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/browser/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05; `BROWSER-01` binary-trust acceptance test added at `modules/browser/tests/acceptance_browser_binary_trust.py`, on 2026-10-24.
- In Progress: None.
- Next Action: `BROWSER-02`, DOM-selector mapping for navigation retry paths.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| BROWSER-01 | P0 | Done | None | Add an acceptance scenario proving a PATH-discovered browser binary that fails the ownership check is refused even when no managed build is present. | 2026-10-24 | FR-BROWSER-001 |
| BROWSER-02 | P1 | Done | None | None — the pinned DOM fixture and `unit_navigation_selector_regression.py` fail the browser suite on selector drift. | 2026-10-24 | FR-BROWSER-002 |
| BROWSER-03 | P2 | Ready | `SESSION-01` | Specify session-directory permission repair for a host that launches the context under a different user. | 2026-10-05 | FR-BROWSER-001, FR-BROWSER-002 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A launch yields an authenticated page and tears down on caller exception | Automated | `modules/browser/tests/unit_agent_browser_orchestrator.py` | open session teardown | 2026-10-05 |
| A login-redirected page raises an authentication error | Automated | `modules/browser/tests/unit_browser_adapter.py` | check auth | 2026-10-05 |
| A non-owner-only session directory is repaired to `0700` | Automated | `modules/browser/tests/unit_browser_adapter.py` | session dir permissions | 2026-10-05 |
| A PATH-discovered binary that fails the ownership check is refused | Automated | `modules/browser/tests/acceptance_browser_binary_trust.py` | test_acceptance_path_binary_with_foreign_owner_is_refused_without_managed_build / test_acceptance_no_trusted_binary_raises_browser_launch_error | 2026-10-24 |
| A navigation retry path whose DOM selector drifts is caught by the browser suite | Automated | `modules/browser/tests/unit_navigation_selector_regression.py` | pinned navigation selectors | 2026-10-24 |

## Blockers

None.

## Dependencies

- `SESSION-01` owns the session pool this feature's context launches over.
- `PROMPT-01` owns the retry budget the navigation path reuses.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/browser/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 5 of 5 scenarios mapped. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-24 | `BROWSER-02` closed: pinned DOM fixture and `unit_navigation_selector_regression.py` map every navigation retry path to its selector; drift fails the browser suite, not a live run. | @qwen-web-arwaky |
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-24 | Added FRD Ref column mapping backlog rows to FR IDs. | @qwen-web-arwaky |
