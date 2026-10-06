# BACKLOG — Config Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/config/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05.
- In Progress: None.
- Blocked: None.
- Next Action: `CONFIG-01`, the multi-fault finding acceptance gap.

## Backlog

| ID | Priority | State | Health | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|---|
| CONFIG-01 | P1 | Ready | On Track | None | Add an acceptance scenario proving a config with several invalid fields reports every one in one call. | 2026-10-05 |
| CONFIG-02 | P1 | Ready | On Track | `PROMPT-01` | Pin the response-wait ceiling semantics once the retry budget settles. | 2026-10-05 |
| CONFIG-03 | P2 | Ready | On Track | None | Specify the capacity ceiling behavior on a host that reports no usable memory. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| An environment override decides the sandbox verdict | Automated | `modules/config/tests/unit_capability_config_inspection.py` | sandbox report | 2026-10-05 |
| An unparseable ceiling falls back to the default | Automated | `modules/config/tests/unit_agent_config_orchestrator.py` | timeout ceiling | 2026-10-05 |
| A not-yet-existing output directory is accepted | Automated | `modules/config/tests/unit_capability_config_inspection.py` | path resolution | 2026-10-05 |
| A seeded multi-fault config reports every finding | Gap | none yet | see `CONFIG-01` | 2026-10-05 |

## Blockers

None.

## Dependencies

- `PROMPT-01` owns the retry budget the response ceiling coordinates with.
- `SHARED-03` carries the rate-limiter window semantics this ceiling feeds.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/config/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 3 of 4 scenarios mapped; one gap tracked as `CONFIG-01`. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

- The slot resolver's widget mapping stays behind the slot surface; this feature only decides what the values mean.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
