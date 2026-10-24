# BACKLOG — Config Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/config/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05; `CONFIG-01` acceptance scenario on 2026-10-24.
- In Progress: None.
- Next Action: `CONFIG-03`, the capacity-ceiling behavior on a host reporting no usable memory.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated |
|---|---:|---|---|---|---|
| CONFIG-01 | P1 | Done | None | None — acceptance scenario proving a config with several invalid fields reports every one in one call. | 2026-10-24 |
| CONFIG-02 | P1 | Done | `PROMPT-01` | None — `timeout_sec` is the absolute per-attempt response ceiling (FR-PROMPT-006), pinned with PROMPT-01 on 2026-10-22. | 2026-10-22 |
| CONFIG-03 | P2 | Ready | None | Specify the capacity ceiling behavior on a host that reports no usable memory. | 2026-10-05 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| An environment override decides the sandbox verdict | Automated | `modules/config/tests/unit_capability_config_inspection.py` | sandbox report | 2026-10-05 |
| An unparseable ceiling falls back to the default | Automated | `modules/config/tests/unit_agent_config_orchestrator.py` | timeout ceiling | 2026-10-05 |
| A not-yet-existing output directory is accepted | Automated | `modules/config/tests/unit_capability_config_inspection.py` | path resolution | 2026-10-05 |
| A seeded multi-fault config reports every finding | Automated | `modules/config/tests/acceptance_config_finding_completeness.py` | `test_acceptance_every_violation_is_reported_in_one_call` | 2026-10-24 |

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

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
