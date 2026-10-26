# BACKLOG — Prompt Runtime Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-26

## Current Condition

- Done: `uv run python -m pytest modules/prompt_runtime/tests/ -m "not benchmark and not e2e" -q` green on 2026-10-26 (FR-PROMPT-006..010 tracked by this module).
- In Progress: None.
- Next Action: None — every backlog row is Done.
- The authoritative prompt backlog lives in [modules/prompt/BACKLOG.md](../prompt/BACKLOG.md) (PROMPT-01/02/03, covering all 12 prompt FRs); this view tracks the runtime layer's share of that work.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| FR-PROMPT-006 | P1 | Done | `CONFIG-02` | Stream-monitor stall detection and the send-dispatcher parse-toast hold coordinated with CONFIG-02; stall-ceiling interaction pinned by `unit_capability_stream_monitor.py`, `unit_capability_stream_resilience.py`, and `unit_capability_send_dispatcher.py`. Evidence: `uv run python -m pytest modules/prompt_runtime/tests/unit_capability_stream_monitor.py modules/prompt_runtime/tests/unit_capability_stream_resilience.py modules/prompt_runtime/tests/unit_capability_send_dispatcher.py -v` → passed (2026-10-26, commit 7af7b47). | 2026-10-26 | FR-PROMPT-006, FR-PROMPT-008 |
| FR-PROMPT-007 | P1 | Done | `SHARED-02` | The prompt-injector DOM probes and the file-uploader pre-flight validation rely on the shared pinned DOM and validation helpers. Evidence: `uv run python -m pytest modules/prompt_runtime/tests/unit_capability_prompt_injector.py modules/prompt_runtime/tests/unit_capability_prompt_injector_verify.py modules/prompt_runtime/tests/unit_capability_file_uploader.py modules/prompt_runtime/tests/unit_attachment_contract.py -v` → passed (2026-10-26, commit 7af7b47). | 2026-10-26 | FR-PROMPT-007, FR-PROMPT-010 |
| FR-PROMPT-008 | P1 | Done | `SHARED-02` | The send dispatcher clicks the send control and counts the resulting chat turns; the parse-toast hold is pinned by the dispatcher and spinner-regression tests. Evidence: `uv run python -m pytest modules/prompt_runtime/tests/unit_capability_send_dispatcher.py modules/prompt_runtime/tests/unit_parse_spinner_regressions.py -v` → passed (2026-10-26, commit 7af7b47). | 2026-10-26 | FR-PROMPT-008 |
| FR-PROMPT-010 | P1 | Done | `SHARED-02` | The file uploader attaches files with pre-flight validation (100 MiB ceiling); the upload-limit acceptance test pins the ceiling. Evidence: `uv run python -m pytest modules/prompt_runtime/tests/unit_capability_file_uploader.py modules/prompt_runtime/tests/unit_attachment_contract.py modules/prompt/tests/acceptance_attachment_upload_limits.py -v` → passed (2026-10-26, commit 7af7b47). | 2026-10-26 | FR-PROMPT-010 |
| FR-PROMPT-009 | P2 | Done | `SHARED-02` | The output saver writes the response and its XDG-state `.meta.json` sidecar; `dogfood_output_saver.py` pins the sidecar schema. Evidence: `uv run python -m pytest modules/prompt_runtime/tests/unit_capability_output_saver.py modules/prompt_runtime/tests/dogfood_output_saver.py -v` → passed (2026-10-26, commit 7af7b47). | 2026-10-26 | FR-PROMPT-009 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| A stalled stream reports `stalled` (and saves the partial) | Automated | `modules/prompt_runtime/tests/unit_capability_stream_monitor.py` | stall detection | 2026-10-26 |
| A hard response timeout reports `incomplete` | Automated | `modules/prompt_runtime/tests/unit_capability_stream_monitor.py` | hard cutoff | 2026-10-26 |
| An attachment over the upload limit is rejected | Automated | `modules/prompt_runtime/tests/unit_capability_file_uploader.py` | upload limit | 2026-10-26 |
| A saved response carries its run metadata outside the output directory | Automated | `modules/prompt_runtime/tests/dogfood_output_saver.py` | a saved response carries its run metadata | 2026-10-26 |

## Blockers

None.

## Dependencies

- `CONFIG-02` owns the response ceiling this layer's stall detector coordinates with.
- `SHARED-02` owns the pinned DOM helpers the stream monitor, prompt injector, and file uploader read.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/prompt_runtime/tests/ -v` passes at the module-split branch. |
| Scenario evidence | Done | 4 of 4 FRD scenarios mapped across 4 automated rows; no gaps. |
| Docs | Done | [FRD.md](FRD.md) is the runtime view of the authoritative [prompt FRD](../prompt/FRD.md). |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-26 | Split the prompt feature's runtime backlog into this BACKLOG; rows are keyed by the runtime FRD FR-IDs (FR-PROMPT-006/007/009) with refs to the remaining runtime FRs, mirroring the authoritative prompt BACKLOG. | @qwen-web-arwaky |
