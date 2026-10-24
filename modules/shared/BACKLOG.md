# BACKLOG — Shared Kernel

FRD: [DATA.md](DATA.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/shared/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- Done: SHARED-01 acceptance scenario (session restore byte-identity) added to `unit_utility_session_backup.py`, 2026-10-24.
- In Progress: None.
- Next Action: `SHARED-02`, pin DOM query helpers against one captured chat transcript.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|
| SHARED-01 | P1 | Done | None | — | 2026-10-24 |
| SHARED-02 | P1 | Ready | None | Pin the DOM query helpers against one captured chat transcript so selector drift fails the kernel suite before it fails a run. | 2026-10-05 |
| SHARED-03 | P2 | Ready | `CONFIG-02` | Specify the rate-limiter window semantics in `DATA.md` once the shared-flow retry budget settles. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A restored session backup reproduces the target tree | Automated | `modules/shared/tests/unit_utility_session_backup.py` | test_restore_is_byte_identical_after_a_full_corruption_cycle | 2026-10-24 |
| Event names are the closed vocabulary the kernel publishes | Automated | `modules/shared/tests/contract_taxonomy_core_event.py` | event contract | 2026-10-05 |
| Capacity guards reject over-subscribed worker counts | Automated | `modules/shared/tests/unit_utility_capacity.py` | capacity bounds | 2026-10-05 |
| Path helpers resolve XDG roots on every platform | Automated | `modules/shared/tests/unit_utility_env.py` | path resolution | 2026-10-05 |

## Blockers

None.

## Dependencies

- `CONFIG-02` owns the request-timeout ceiling that the flow kernel reads.
- `PROMPT-01` owns the retry budget that the shared rate limiter enforces.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/shared/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 4 of 4 scenarios mapped to an automated test. |
| Docs | Done | [DATA.md](DATA.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-24 | SHARED-01 advanced to Done: acceptance test `test_restore_is_byte_identical_after_a_full_corruption_cycle` added to `unit_utility_session_backup.py`. | @qwen-web-arwaky |
| 2026-10-05 | Initial kernel backlog created with the AES701 doc pair. | @qwen-web-arwaky |
