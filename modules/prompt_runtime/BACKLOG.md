# BACKLOG — Prompt-Runtime Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-27

## Current Condition

- Done: `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` green on 2026-10-27 (RUNTIME-01 aggregate door + the five capability seams routed and proven).
- In Progress: None.
- Next Action: None — every backlog row is Done.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated | FRD Ref |
|---|---:|---|---|---|---|---|
| FR-RUNTIME-001 | P1 | Done | `PROMPT-03` | Inject routes through the shared `IInjectionProtocol`; covered by `modules/prompt_runtime/tests/e2e_prompt_runtime_pipeline.py`. Evidence: `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` → 298 passed (2026-10-27, branch `rakaarwaky/prompt-runtime-split-merge`). | 2026-10-27 | FR-RUNTIME-001, FR-RUNTIME-006 |
| FR-RUNTIME-002 | P1 | Done | `PROMPT-03` | Send dispatch and its turn-count report route through `ISendProtocol`; the ACK gate is covered by `modules/prompt_runtime/tests/unit_capability_send_dispatcher.py` and the routing by `modules/prompt_runtime/tests/e2e_prompt_runtime_pipeline.py`. Evidence: `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` → 298 passed (2026-10-27, branch `rakaarwaky/prompt-runtime-split-merge`). | 2026-10-27 | FR-RUNTIME-002, FR-RUNTIME-006 |
| FR-RUNTIME-003 | P1 | Done | `CONFIG-02` | Watch routes through `IStreamProtocol` and returns the stable text + verdict; stall/ceiling verdicts pinned by `modules/prompt_runtime/tests/unit_capability_stream_monitor.py`. Evidence: `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` → 298 passed (2026-10-27, branch `rakaarwaky/prompt-runtime-split-merge`). | 2026-10-27 | FR-RUNTIME-003, FR-RUNTIME-006 |
| FR-RUNTIME-004 | P1 | Done | None | The 104857600-byte ceiling and allowlist pre-flight are pinned at the boundary by `modules/prompt_runtime/tests/acceptance_runtime_capability_door.py` (over-ceiling rejected, exact-ceiling accepted). Evidence: `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` → 298 passed (2026-10-27, branch `rakaarwaky/prompt-runtime-split-merge`). | 2026-10-27 | FR-RUNTIME-004, FR-RUNTIME-006 |
| FR-RUNTIME-005 | P1 | Done | None | `0o600` artifacts and the metadata-dir sidecar are asserted against a real filesystem by `modules/prompt_runtime/tests/acceptance_runtime_capability_door.py` and `modules/prompt_runtime/tests/integration_prompt_runtime_orchestrator.py`. Evidence: `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` → 298 passed (2026-10-27, branch `rakaarwaky/prompt-runtime-split-merge`). | 2026-10-27 | FR-RUNTIME-005, FR-RUNTIME-006 |
| FR-RUNTIME-006 | P1 | Done | None | The aggregate door refuses unknown verbs and missing required slots with `QwenCliError` (`modules/prompt_runtime/tests/integration_prompt_runtime_orchestrator.py`, `modules/prompt_runtime/tests/acceptance_runtime_capability_door.py`); boot is pinned by `modules/prompt_runtime/tests/smoke_prompt_runtime_orchestrator.py`. Evidence: `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` → 298 passed (2026-10-27, branch `rakaarwaky/prompt-runtime-split-merge`). | 2026-10-27 | FR-RUNTIME-006 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| The aggregate boots over the five real capabilities and routes a verb | Automated | `modules/prompt_runtime/tests/integration_prompt_runtime_orchestrator.py` | `test_integration_orchestrator_boots_with_the_five_real_capabilities` | 2026-10-27 |
| A verb outside the runtime set is refused by name | Automated | `modules/prompt_runtime/tests/acceptance_runtime_capability_door.py` | `test_acceptance_a_verb_outside_the_runtime_set_is_refused` | 2026-10-27 |
| A persisted response is `0o600` on disk | Automated | `modules/prompt_runtime/tests/acceptance_runtime_capability_door.py` | `test_acceptance_a_persisted_artifact_is_private` | 2026-10-27 |
| The `.meta.json` sidecar lands in the metadata dir, never beside the artifact | Automated | `modules/prompt_runtime/tests/acceptance_runtime_capability_door.py` | `test_acceptance_the_sidecar_lands_in_the_metadata_dir_not_beside_the_output` | 2026-10-27 |
| An attachment over 104857600 bytes is rejected pre-flight; one exactly at the ceiling passes | Automated | `modules/prompt_runtime/tests/acceptance_runtime_capability_door.py` | `test_acceptance_an_oversized_attachment_is_rejected_before_the_browser`, `test_acceptance_a_boundary_attachment_fits_the_ceiling` | 2026-10-27 |
| `persist` writes the artifact and its sidecar to a real temporary directory | Automated | `modules/prompt_runtime/tests/integration_prompt_runtime_orchestrator.py` | `test_integration_persist_verb_writes_a_real_file` | 2026-10-27 |
| A completed stream reports the stable text and a `complete` verdict through the door | Automated | `modules/prompt_runtime/tests/integration_prompt_runtime_orchestrator.py` | `test_integration_emit_a_verdict_from_a_completed_stream` | 2026-10-27 |
| A `send`/`watch` without an emitter, an `upload` without a file, and a `persist` without a destination are refused at the door | Automated | `modules/prompt_runtime/tests/integration_prompt_runtime_orchestrator.py` | `test_integration_watch_verb_needs_an_emitter`, `test_integration_send_verb_needs_an_emitter`, `test_integration_upload_verb_needs_a_file`, `test_integration_persist_verb_needs_a_destination` | 2026-10-27 |
| The full runtime lifecycle runs through one door end to end (upload → inject → send → watch → persist) | Automated | `modules/prompt_runtime/tests/e2e_prompt_runtime_pipeline.py` | `test_e2e_the_runtime_lifecycle_runs_through_one_door` | 2026-10-27 |
| The aggregate boots and persists one artifact in well under five seconds | Automated | `modules/prompt_runtime/tests/smoke_prompt_runtime_orchestrator.py` | `test_smoke_the_aggregate_boots_and_persists_one_artifact` | 2026-10-27 |

## Blockers

None.

## Dependencies

- `PROMPT-03`/`modules/prompt` owns the inject → send → wait ordering this feature does not duplicate; the runtime verbs are the seam it hands work to.
- `CONFIG-02` owns the dispatch retry budget and response ceiling the stream monitor coordinates with.
- The shared protocol seams live in `modules/shared/src/prompt/contract_prompt_protocol.py` (declared by the prompt feature).

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/prompt/tests/ modules/prompt_runtime/tests/ modules/prompt/benches/ modules/prompt_runtime/benches/ -m "not benchmark"` → 298 passed (2026-10-27). |
| Scenario evidence | Done | 10 automated rows covering FR-RUNTIME-001..006; no gaps. |
| Docs | Done | [FRD.md](FRD.md) is specification-only; [DESIGN.md](DESIGN.md) points at this FRD. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-27 | Feature FRD, BACKLOG, and the `IPromptRuntimeAggregate` door created; 10 scenario-evidence rows recorded from the 298-pass run. | @qwen-web-arwaky |
