# BACKLOG — Browser Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/browser/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Blocked: None.
- Next Action: `BROWSER-01`, the binary-trust acceptance gap.

## Backlog

| ID | Priority | State | Health | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|---|
| BROWSER-01 | P0 | Ready | At Risk | None | Add an acceptance scenario proving a PATH-discovered browser binary that fails the ownership check is refused even when no managed build is present. | 2026-10-05 |
| BROWSER-02 | P1 | Ready | On Track | None | Map every navigation retry path to a pinned DOM selector so a selector drift fails the browser suite, not a live run. | 2026-10-05 |
| BROWSER-03 | P2 | Ready | On Track | `SESSION-01` | Specify session-directory permission repair for a host that launches the context under a different user. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A launch yields an authenticated page and tears down on caller exception | Automated | `modules/browser/tests/unit_agent_browser_orchestrator.py` | open session teardown | 2026-10-05 |
| A login-redirected page raises an authentication error | Automated | `modules/browser/tests/unit_browser_adapter.py` | check auth | 2026-10-05 |
| A non-owner-only session directory is repaired to `0700` | Automated | `modules/browser/tests/unit_browser_adapter.py` | session dir permissions | 2026-10-05 |
| A PATH-discovered binary that fails the ownership check is refused | Gap | none yet | see `BROWSER-01` | 2026-10-05 |

## Blockers

None.

## Dependencies

- `SESSION-01` owns the session pool this feature's context launches over.
- `PROMPT-01` owns the retry budget the navigation path reuses.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/browser/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 3 of 4 scenarios mapped; one gap tracked as `BROWSER-01`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

- Managed-build-only binary discovery for hosts that cannot run any sandbox stays behind the environment verdict.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
