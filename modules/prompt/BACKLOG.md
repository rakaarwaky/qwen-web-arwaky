# BACKLOG — Prompt Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/prompt/tests/ -m "not benchmark and not e2e" -q` green on 2026-10-24 (PROMPT-01 dispatch retry budget coordinated with CONFIG-02).
- In Progress: None.
- Next Action: None — every backlog row is Done.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| PROMPT-01 | P1 | Done | `CONFIG-02` | None — retry budget coordinated with CONFIG-02; stall-ceiling interaction pinned by `unit_transcript_selector_regression.py`, `unit_agent_shared_flow_retry.py`, and `unit_prompt_dispatch_retry_budget.py`. | 2026-10-24 | FR-PROMPT-001, FR-PROMPT-002, FR-PROMPT-003, FR-PROMPT-006, FR-PROMPT-007, FR-PROMPT-009, FR-PROMPT-010 |
| PROMPT-02 | P1 | Done | None | None — covered by `modules/prompt/tests/unit_agent_cancel_terminal.py`. | 2026-10-22 | FR-PROMPT-004, FR-PROMPT-005 |
| PROMPT-03 | P2 | Done | `SHARED-02` | None — the pinned transcript fixture and `unit_transcript_selector_regression.py` fail the prompt suite on selector drift. | 2026-10-22 | FR-PROMPT-008, FR-PROMPT-011, FR-PROMPT-012 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A direct prompt produces a response file at the named destination | Automated | `modules/prompt/tests/unit_agent_direct_prompt.py` | direct prompt save | 2026-10-22 |
| A saved response carries its run metadata outside the output directory | Automated | `modules/prompt/tests/dogfood_output_saver.py` | a saved response carries its run metadata | 2026-10-22 |
| A stalled stream reports `stalled` (and saves the partial) | Automated | `modules/prompt/tests/unit_capability_stream_monitor.py` | stall detection | 2026-10-22 |
| A hard response timeout reports `incomplete` | Automated | `modules/prompt/tests/unit_capability_stream_monitor.py` | hard cutoff | 2026-10-22 |
| An attachment over the upload limit is rejected | Automated | `modules/prompt/tests/unit_capability_file_uploader.py` | upload limit | 2026-10-05 |
| A cancel on a terminal pipeline reports zero | Automated | `modules/prompt/tests/unit_agent_cancel_terminal.py` | `test_cancel_on_a_terminal_pipeline_reports_zero` | 2026-10-22 |
| A cancel on a file pipeline reports one stopped pipeline | Automated | `modules/prompt/tests/unit_agent_cancel_terminal.py` | `test_cancel_on_an_in_flight_file_pipeline_reports_one_stopped_pipeline` | 2026-10-22 |
| A response file survives a mid-stream extraction failure | Automated | `modules/prompt/tests/unit_agent_prompt_file.py` | `test_stalled_stream_saves_the_partial_artifact_with_a_stalled_verdict` | 2026-10-22 |
| A cancel for a run with no active pipeline is a no-op and does not affect sibling runs | Automated | `modules/prompt/tests/unit_agent_cancel_terminal.py` | `test_cancel_on_a_terminal_pipeline_reports_zero`, `test_cancel_on_one_pipeline_leaves_the_sibling_run_alone` | 2026-10-22 |

## Blockers

None.

## Dependencies

- `CONFIG-02` owns the response ceiling this feature's stall detector coordinates with.
- `SHARED-02` owns the pinned DOM helpers the stream monitor reads.
- `JOBS-01` owns the backpressure this feature's job submissions encounter.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/prompt/tests/ -v` passes at `refactor/aes-zero-violations`. |
| Scenario evidence | Done | 6 of 6 FRD scenarios mapped across 7 automated rows; no gaps. |
| Docs | Done | [FRD.md](FRD.md) is specification-only. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-25 | Closed FR-orphan gaps: FR-PROMPT-002/007/009/010 attached to PROMPT-01, FR-PROMPT-011/012 to PROMPT-03; ROADMAP roll-up advanced to Done. | @qwen-web-arwaky |
| 2026-10-24 | Added FRD Ref column mapping backlog rows to FR IDs. | @qwen-web-arwaky |
| 2026-10-24 | PROMPT-01 closed: dispatch retry budget coordinated with CONFIG-02 (`unit_prompt_dispatch_retry_budget.py`). | @qwen-web-arwaky |
| 2026-10-22 | Scenario evidence completed (7 automated rows, 0 gaps); `PROMPT-02`/`PROMPT-03` closed; `PROMPT-01` stall-ceiling pinning done, retry budget remains with `CONFIG-02`. | @qwen-web-arwaky |
| 2026-10-05 | Feature FRD and BACKLOG created alongside the AES702 doc pair. | @qwen-web-arwaky |
| 2026-10-22 | Sidecars moved to `DEFAULT_METADATA_DIR` (XDG state `meta/`); direct-prompt outputs named `direct_*` instead of `tmpXXXX_*` (FR-PROMPT-009). | @qwen-web-arwaky |
