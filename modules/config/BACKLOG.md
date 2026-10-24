# BACKLOG — Config Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-05

## Current Condition

- Done: `uv run python -m pytest modules/config/tests/ -v` at commit `refactor/aes-zero-violations`, on 2026-10-05; CONFIG-03 pinned on 2026-10-24.
- In Progress: None.
- Next Action: `CONFIG-01`, the multi-fault finding acceptance gap.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| CONFIG-01 | P1 | Ready | None | Add an acceptance scenario proving a config with several invalid fields reports every one in one call. | 2026-10-05 | FR-CONFIG-002 |
| CONFIG-02 | P1 | Done | `PROMPT-01` | None — `timeout_sec` is the absolute per-attempt response ceiling (FR-PROMPT-006), pinned with PROMPT-01 on 2026-10-22. | 2026-10-22 | FR-CONFIG-001 |
| CONFIG-03 | P2 | Done | None | None — capacity ceiling returns the single-worker default when the host reports no usable memory (FR-CONFIG-004), pinned in `unit_capability_config_inspection.py`. | 2026-10-24 | FR-CONFIG-003, FR-CONFIG-004, FR-CONFIG-005, FR-CONFIG-006, FR-CONFIG-007 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| An environment override decides the sandbox verdict | Automated | `modules/config/tests/unit_capability_config_inspection.py` | sandbox report | 2026-10-05 |
| An unparseable ceiling falls back to the default | Automated | `modules/config/tests/unit_agent_config_orchestrator.py` | timeout ceiling | 2026-10-05 |
| A not-yet-existing output directory is accepted | Automated | `modules/config/tests/unit_capability_config_inspection.py` | path resolution | 2026-10-05 |
| A host that reports no usable memory falls back to one worker | Automated | `modules/config/tests/unit_capability_config_inspection.py` | capacity fallback | 2026-10-24 |
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

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-25 | ROADMAP roll-up advanced to Done; FR-orphan refs added: FR-CONFIG-001 to CONFIG-02, FR-CONFIG-002 to CONFIG-01, FR-CONFIG-003/005/006/007 to CONFIG-03 (closest rows). | @qwen-web-arwaky |
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
