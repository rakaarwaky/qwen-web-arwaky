# Feature Backlog: Core Automation Engine

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md) — do not redefine here.
Last Updated: 2026-09-24

## Current Condition

- Done: `PYTHON=.venv/bin/python bash scripts/verify_core_backlog.sh` → 50 passed at `d8a9b60`, on 2026-09-24.
- In Progress: None.
- Blocked: None.
- Next Action: close the live-browser verification gaps recorded for CORE-01, CORE-02, CORE-04, and CORE-06.

## Backlog

| ID | FRD Ref | Work Item | Priority | State | Actual Condition | Owner | Dependencies | Updated |
|---|---|---|---:|---|---|---|---|---|
| CORE-01 | FR-001 | Maintain persistent authenticated browser lifecycle and thread isolation. | P0 | Done | Stale-lock cleanup is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_browser_adapter.py::test_clean_stale_locks` at `d8a9b60`; live authentication remains mapped as Manual below. | @maintainers | Qwen Web DOM, Chromium | 2026-09-24 |
| CORE-02 | FR-002 | Validate and attach local files with safe text-only degradation. | P0 | Done | Oversize rejection is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_capability_file_uploader.py::TestValidateFile::test_file_too_large` at `d8a9b60`; live card rendering remains mapped as Manual below. | @maintainers | Qwen Web DOM | 2026-09-24 |
| CORE-03 | FR-003 | Persist responses atomically with metadata. | P0 | Done | Atomic output is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_capability_output_saver.py::TestWriteFileAtomic::test_atomic_write` at `d8a9b60`. | @maintainers | None | 2026-09-24 |
| CORE-04 | FR-004 | Inject and verify prompt text through resilient DOM strategies. | P0 | Done | Empty-input rejection is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_capability_prompt_injector.py::TestInjectTextStrategies::test_empty_text_raises` at `d8a9b60`; the 100k live-DOM case remains a Gap below. | @maintainers | Qwen Web DOM | 2026-09-24 |
| CORE-05 | FR-005 | Dispatch only after readiness gates and prove acknowledgement. | P0 | Done | Dispatch acknowledgement is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_capability_send_dispatcher.py::test_ack_observed_via_user_bubble_count` at `d8a9b60`. | @maintainers | CORE-02 | 2026-09-24 |
| CORE-06 | FR-006 | Monitor streaming to validated completion with timeout and recovery controls. | P0 | Done | Stable-response completion is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_capability_stream_monitor.py::TestWaitForResponseEdgeCases::test_returns_stable_text` at `d8a9b60`; end-to-end cloud reload remains Manual below. | @maintainers | Qwen Web DOM | 2026-09-24 |
| CORE-07 | FR-007 | Provision an idempotent XDG workspace and skill links. | P0 | Done | Initialization behavior is verified by `.venv/bin/python -m pytest -q modules/cli/tests/integration_surface_init_cmd.py` at `d8a9b60`. | @maintainers | Filesystem symlink support | 2026-09-24 |
| CORE-08 | FR-008 | Bootstrap optional telemetry and structured local logging without blocking startup. | P0 | Done | CLI logging behavior is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_observability_stderr.py::test_cli_mode_still_attaches_stderr_handler` at `d8a9b60`. | @maintainers | Optional Sentry and OTLP endpoints | 2026-09-24 |
| CORE-09 | FR-009 | Compile folders with import-aware, boundary-safe traversal. | P0 | Done | Import-aware compilation is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_folder_compiler.py::TestFolderCompilerImportAware::test_compile_folder_include_imports` at `d8a9b60`. | @maintainers | None | 2026-09-24 |
| CORE-10 | FR-010 | Convert compiled folders into uploadable attachments. | P0 | Done | Adapter paths are covered by `.venv/bin/python -m pytest -q modules/core/tests/unit_folder_compiler.py` at `d8a9b60` as recorded by FRD traceability. | @maintainers | CORE-09, CORE-02 | 2026-09-24 |
| CORE-11 | FR-011 | Persist, execute, and poll bounded asynchronous jobs. | P0 | Done | Storage and parallel orchestration are verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_capability_job_manager.py::TestJobManager::test_save_and_get_job modules/core/tests/integration_parallel_jobs.py::test_agent_job_orchestrator_runs_n_jobs_in_parallel` at `d8a9b60`. | @maintainers | CORE-01 | 2026-09-24 |
| CORE-12 | FR-012 | Resolve validated per-slot TUI execution plans. | P0 | Done | Slot and TUI behavior are verified by `.venv/bin/python -m pytest -q modules/cli/tests/unit_surface_cli_tui_app.py` at `d8a9b60`. | @maintainers | CLI surface | 2026-09-24 |
| CORE-13 | FR-013 | Check and apply package updates while synchronizing browser health. | P0 | Done | Update behavior is verified by `.venv/bin/python -m pytest -q modules/cli/tests/unit_surface_cli_update_command.py` at `d8a9b60`. | @maintainers | Package index, Chromium | 2026-09-24 |
| CORE-14 | CR-2026-004 | Fan out role templates with bounded concurrency, retry, cancellation, and partial results. | P1 | Done | Partial-result retry is verified by `.venv/bin/python -m pytest -q modules/core/tests/unit_agent_swarm_orchestrator.py::test_swarm_retries_transient_agent_failure_and_allows_partial` at `d8a9b60`. | @maintainers | CORE-02, CORE-09, CORE-10 | 2026-09-24 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| FR-001: expired cookies raise `AuthRequiredError` and point the user at `qwen-web-arwaky login`. | Automated | modules/core/tests/unit_browser_adapter.py | `test_session_check_auth_redirect` | `d8a9b60` |
| FR-001: a valid persistent profile is reused by a live browser. | Manual | modules/core/tests/integration_browser_session.py | `test_browser_session_headless` (requires installed Chromium and authenticated profile) | Not run 2026-09-24 |
| FR-002: attach card appears on fixture; oversized file never opens chooser. | Proxy | modules/core/tests/unit_capability_file_uploader.py | `TestValidateFile.test_file_too_large` and `TestUploadAttachment.test_upload_returns_true` | `d8a9b60` |
| FR-003: killing the process during write leaves no half file (atomic). | Proxy | modules/core/tests/unit_capability_output_saver.py | `TestWriteFileAtomic.test_atomic_write` | `d8a9b60` |
| FR-004: 100k-char prompt injects via React setter on fixture. | Gap | modules/core/tests/unit_capability_prompt_injector.py | No 100k-character fixture scenario exists. | Not verified |
| FR-005: send is refused while attachment parse gate is false. | Automated | modules/core/tests/unit_parse_spinner_regressions.py | `TestWaitForSendEnabledHoldFlag.test_hold_when_not_parsed` | `d8a9b60` |
| FR-006: circuit of Stop button → streaming text → stable text completes. | Proxy | modules/core/tests/unit_capability_stream_monitor.py | `TestWaitForResponseEdgeCases.test_returns_stable_text` | `d8a9b60` |
| FR-006: proactive cloud reload recovers a live long-running stream. | Manual | modules/core/tests/unit_capability_stream_monitor.py | Unit recovery coverage exists; live Qwen run required for end-to-end proof. | Not run 2026-09-24 |
| FR-007: second `init` is idempotent. | Automated | modules/cli/tests/integration_surface_init_cmd.py | `TestQwaInit.test_run_init_idempotent_and_existing_gitignore` | `d8a9b60` |
| FR-008: process starts with empty `SENTRY_DSN` and no OTLP endpoint. | Automated | modules/core/tests/unit_utility_dom_query.py | `TestObservabilityRemaining.test_configure_sentry_no_dsn`, `TestObservabilityRemaining.test_configure_tracing_no_otel` | `d8a9b60` |
| FR-009: imports outside the selected folder compile only inside the workspace boundary. | Automated | modules/core/tests/unit_folder_compiler.py | `TestImportBoundaryConfinement.test_import_outside_explicit_boundary_refused` | `d8a9b60` |
| FR-010: folder compilation produces an uploadable attachment path. | Proxy | modules/core/tests/unit_folder_compiler.py | Folder compiler adapter-path coverage listed in FRD traceability. | `d8a9b60` |
| FR-011: bounded jobs run in parallel and remain independently queryable. | Automated | modules/core/tests/integration_parallel_jobs.py | `test_agent_job_orchestrator_runs_n_jobs_in_parallel` | `d8a9b60` |
| FR-012: TUI slot inputs resolve to validated execution plans. | Automated | modules/cli/tests/unit_surface_cli_tui_app.py | TUI slot-planning suite | `d8a9b60` |
| FR-013: update checks and update outcomes are surfaced safely. | Automated | modules/cli/tests/unit_surface_cli_update_command.py | Update command suite | `d8a9b60` |
| CR-2026-004: transient agent failure retries and permits a partial result. | Automated | modules/core/tests/unit_agent_swarm_orchestrator.py | `test_swarm_retries_transient_agent_failure_and_allows_partial` | `d8a9b60` |

Kind values: Automated, Proxy, Manual, Gap.

## Blockers

None. Manual and gap scenarios reduce evidence completeness but do not block the currently shipped implementation. The FR-004 gap clears when an automated 100k-character fixture test is added.

## Dependencies

- CORE-01, CORE-02, CORE-04, and CORE-06 depend on the external Qwen Web DOM remaining compatible.
- CORE-08 depends on optional telemetry services only when those integrations are enabled.
- CORE-13 depends on package-index and Chromium availability for a real update.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `PYTHON=.venv/bin/python bash scripts/verify_core_backlog.sh` → 50 passed at `d8a9b60` on 2026-09-24. |
| Scenario evidence | In Progress | 12 automated/proxy mappings, 2 manual mappings, and 1 explicit gap for the Core FR scenarios. |
| Docs | Done | `python scripts/check_docs.py .` → passed at `32e30f1` on 2026-09-24. |

## Deferred

- Automated 100k-character React-controlled prompt injection scenario — deferred until the representative DOM fixture is available.
- Live authenticated browser, attachment-card, and long-stream recovery runs — deferred because they require a user-owned Qwen session and current external UI.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-09-24 | Created the evidence-backed feature baseline from implementation at `d8a9b60`; recorded manual checks and the 100k-character gap honestly. | @arena-agent |
