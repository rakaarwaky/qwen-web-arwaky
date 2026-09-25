# FRD — Core Automation Engine

## System Overview

The Core module (`modules/core`) is the automation engine for `chat.qwen.ai`.
It implements the AES Capabilities and Agent layers: Playwright browser
  lifecycle, local file attach, prompt injection, send dispatch, stream
  stability, output persistence, workspace setup, audit, and observability.

**AES mapping rule:** 1 FR = 1 capability file + 1 contract protocol.

## Functional Requirements

### FR-001: Browser Adapter

- **Capability**: `capabilities_browser_adapter.py` → `BrowserAdapter`
- **Contract**: `IBrowserProtocol`
- **Description**: Launch and tear down a persistent Chromium context,
  navigate to `https://chat.qwen.ai/`, and prove the session is authenticated
  before any DOM work.
- **Input**: `AppConfig` (`session_path`, `headless`, `mode`), `Page`,
  `LifecycleEmitter`.
- **Output**: `BrowserContext` (context manager), `bool` session check,
  domain events (`EVENT_WEB_LOADED`, `EVENT_NETWORK_RECONNECTING`).
- **Business Rules**:
  - Must use `launch_persistent_context` so cookies and LocalStorage survive
    across runs.
  - Must delete stale Chromium singleton files (`SingletonLock`,
    `SingletonSocket`, `SingletonCookie`) before each launch attempt.
  - Must set session directory permissions to `0o700` so Chromium can create
    its process lock without exposing the profile to group/other.
  - Must retry launch 3 times with a 2s wait (tenacity) after cleaning locks.
  - Must isolate the thread event loop before `sync_playwright()`.
  - Must block image/font/media routes when `mode != "login"` to cut traffic.
  - Must prefer a discovered system Chrome binary when present.
  - Auth is a triple-check: URL keywords (`login`, `passport`, `auth`,
    `signin`, `account`, `sso`), visible login-form selectors, and presence of
    `textarea.message-input-textarea`.
  - `check_session` is stricter than `check_auth`: page must be ready, chat
    textarea present, and no login form.
  - Default-model policy (issue #374): `ensure_default_model` is best-effort
    and never blocks the pipeline; `_verify_default_model` then confirms the
    active model. If a *different* model label is readable — a rename,
    regional substitution, or picker DOM drift — the pipeline **proceeds with
    the active model** and `EVENT_MODEL_VERIFIED` carries the detected name
    with `fallback: true`. Only an unreadable picker raises
    `ModelSwitchError`, because the active model is then unknowable. This is
    the specified fallback: availability outranks exact-name matching.
- **Edge Cases**: stale profile after crash; missing execute bit on an
  existing session dir; concurrent Chromium instances; headed login vs
  headless prompt-only; user closes the page mid-navigation; load-state wait times
  out while the chat UI is already usable.
- **Error Handling**:
  - `BrowserLaunchError` after launch retries are exhausted.
  - `AuthRequiredError` when the page is a login/auth surface.
  - Playwright `Error` during reset is logged and does not crash the adapter.
- **Acceptance Criteria**:
  - [ ]  Persistent profile is reused; a second launch does not require login
    when cookies are valid.
  - [ ]  Stale `SingletonLock` does not block a subsequent launch.
  - [ ]  Session dir is `0o700` after `browser_session` enters.
  - [ ]  Login URL or visible password form raises `AuthRequiredError`.
  - [ ]  Media/font/image requests are aborted outside login mode.
- **Tests**: `tests/unit_browser_adapter.py`,
  `tests/integration_browser_session.py`, `tests/integration_surface_login.py`.

### FR-002: File Uploader

- **Capability**: `capabilities_file_uploader.py` → `FileUploader`
- **Contract**: `IUploadProtocol`
- **Description**: Pre-flight validate a local file and attach it through the
  Qwen Web UI file chooser so the model can parse the document.
- **Input**: `Page`, `Path`, optional `UploadConfig` / override dict,
  `LifecycleEmitter`, `web_loaded` gate.
- **Output**: `bool` (True on attach success). Emits `EVENT_DOCUMENT_PARSED`
  with file path and byte size.
- **Business Rules**:
  - Must refuse upload when `web_loaded` is false.
  - Must validate existence, regular-file type, read permission, and size
    (default max 100 MB) before touching the DOM.
  - Must open the mode-select dropdown, click "Upload attachment", fulfill
    `expect_file_chooser`, and wait for a file-card selector to become visible.
  - Must retry up to `max_retries + 1` attempts with linear backoff
    (`backoff_delay_sec * attempt`).
  - Must press Escape between failed attempts to close an orphaned dropdown.
  - Agent fallback: if upload returns False, processing continues as
    text-only and the agent still emits `EVENT_DOCUMENT_PARSED`.
- **Edge Cases**: missing file; directory path; unreadable file; oversized
  file; dropdown not found after UI drift; file chooser timeout; card never
  renders; spinner/parsing indicator lingers.
- **Error Handling**:
  - `FileValidationError` during `validate_file` (public API).
  - `upload_attachment` returns `False` on validation failure or exhausted
    retries (does not raise) so the agent can degrade to text-only.
  - Playwright `TimeoutError` / `Error` are logged, dropdown is closed, then
    retry.
- **Acceptance Criteria**:
  - [ ]  Non-existent or oversized file fails validation and does not open
    the chooser.
  - [ ]  Happy path: dropdown → "Upload attachment" → chooser → visible card
    → `True`.
  - [ ]  Transient timeout retries then returns `False` after max attempts.
  - [ ]  Upload is blocked when `web_loaded` is false.
- **Tests**: `tests/unit_capability_file_uploader.py`, `tests/contract_qwen_auto.py`.

### FR-003: Output Saver

- **Capability**: `capabilities_output_saver.py` → `Saver`
- **Contract**: `ISaverProtocol`
- **Description**: Persist the extracted AI response to disk with an optional
  metadata header and JSON sidecar, using atomic writes by default.
- **Input**: output `Path`, response `content`, `RunContext`, source path,
  duration seconds, `input_chars`, `output_chars`, optional `SaverConfig`.
- **Output**: UTF-8 markdown file at `path`; optional `path.with_suffix(".meta.json")`.
- **Business Rules**:
  - Defaults: `include_header=True`, `generate_sidecar=True`, `atomic_write=True`.
  - Header is built from run id, source, duration, and char counts.
  - UI chrome noise is stripped (`strip_ui_noise`) before write.
  - Parent directories are created before any write.
  - Atomic path: write temp then replace. Non-atomic path: direct `write_text`.
  - Sidecar failure is logged and must not fail the primary write.
- **Edge Cases**: missing parent dirs; disk full; permission denied; content
  containing UI tags; config passed as dict vs dataclass.
- **Error Handling**:
  - `OutputWriteError` when directory create or primary file write fails.
  - Sidecar `OSError` / `TypeError` / `ValueError` is logged only.
- **Acceptance Criteria**:
  - [ ]  Output file contains header + cleaned body when header is enabled.
  - [ ]  Sidecar JSON includes `run_id`, `source_file`, `processed_at`,
    `duration_sec`, `input_chars`, `output_chars`.
  - [ ]  Crash mid-write does not leave a truncated destination when atomic.
  - [ ]  Sidecar I/O error still leaves the markdown file intact.
- **Tests**: `tests/unit_capability_output_saver.py`.

### FR-004: Prompt Injector

- **Capability**: `capabilities_prompt_injector.py` → `PromptInjector`
- **Contract**: `IInjectionProtocol`
- **Description**: Locate the Qwen chat input and inject prompt text using a
  four-tier strategy that survives React/ContentEditable UI drift.
- **Input**: `Page`, `PromptText`, optional `InjectorConfig`.
- **Output**: None (mutates DOM). Verified non-empty input value when
  `verify_injection` is true.
- **Business Rules**:
  - Empty or whitespace-only text is rejected.
  - Input lookup uses `InjectorConfig.input_selectors` in order, then a full
    timeout on the primary selector.
  - Tiers, in order:
    1. React `HTMLTextAreaElement.prototype.value` setter + `input`/`change`.
    2. ContentEditable `innerText` setter + `input`.
    3. Playwright `fill()`.
    4. Playwright `type()` with `typing_delay_ms`.
  - A tier succeeds only if it returns success **and** verification passes
    (unless `verify_injection` is false).
- **Edge Cases**: hidden/detached textarea; React state not synced; 100k+
  character prompts; UI class rename; focus() failure (logged, not fatal).
- **Error Handling**:
  - `ElementNotFoundError` if no input selector matches.
  - `PromptInjectionError` if text is empty, all tiers throw, or verification
    fails after every tier.
- **Acceptance Criteria**:
  - [ ]  Primary selector `textarea.message-input-textarea` is found on the
    fixture DOM.
  - [ ]  React setter path succeeds for a normal textarea.
  - [ ]  Empty prompt raises `PromptInjectionError` before any DOM write.
  - [ ]  All-tier failure raises `PromptInjectionError`.
- **Tests**: `tests/unit_capability_prompt_injector.py`,
  `tests/unit_capability_prompt_injector_verify.py`, `tests/contract_qwen_auto.py`.

### FR-005: Send Dispatcher

- **Capability**: `capabilities_send_dispatcher.py` → `SendDispatcher`
- **Contract**: `ISendProtocol`
- **Description**: Submit the prepared prompt (and optional attachment) and
  expose chat-turn inspection helpers used as the stream baseline.
- **Input**: `Page`, `LifecycleEmitter`, optional `SenderConfig`,
  `document_parsed` gate.
- **Output**: None for click. `MessageCount` / `ResponseText` for inspectors.
  Emits `EVENT_SEND_CLICKED`.
- **Business Rules**:
  - Must refuse send when `document_parsed` is false (attachment still
    parsing).
  - Click uses multi-selector send helpers (`button[aria-label*='Send']`,
    submit, class/id fallbacks) with an optional Enter-key fallback.
  - An explicit per-call `SenderConfig` overrides the instance default; Enter is
    attempted only when `try_enter_key_fallback` is true.
  - `count_messages` is the pre-send baseline for FR-006.
  - `latest_message_text` returns the longest non-chrome text block.
- **Edge Cases**: send button disabled while file is parsing; selector drift;
  empty chat log; page closed between inject and click.
- **Error Handling**:
  - `SendDispatchError` when the parse gate is not satisfied or all click
    strategies fail.
- **Acceptance Criteria**:
  - [ ]  Click is blocked when `document_parsed` is false.
  - [ ]  Successful click emits `EVENT_SEND_CLICKED`.
  - [ ]  `count_messages` matches assistant/turn nodes on the fixture.
  - [ ]  Enter fallback is attempted when the send button is not clickable and
    enabled by configuration.
  - [ ]  Disabled fallback never presses Enter and failed dispatch raises
    `SendDispatchError` without emitting `EVENT_SEND_CLICKED`.
- **Tests**: `tests/unit_capability_send_dispatcher.py`, `tests/contract_qwen_auto.py`.

### FR-006: Stream Monitor

- **Capability**: `capabilities_stream_monitor.py` → `StreamMonitor`
- **Contract**: `IStreamProtocol`
- **Description**: Poll the DOM until the assistant response is stable and
  generation UI (Stop / disabled Send / typing) has cleared, then validate
  the text is not a CAPTCHA or error page.
- **Input**: `Page`, `timeout_sec`, `msg_count_before`, `LifecycleEmitter`,
  poll/stability/min-length knobs, `dispatch_acknowledged` gate.
- **Output**: `ResponseText` on the terminal generation event.
  Events: `EVENT_THINKING_STARTED`, `EVENT_STREAMING_GENERATION`,
  `EVENT_GENERATION_FINISHED`.
- **Business Rules**:
  - Must refuse wait when `dispatch_acknowledged` is false.
  - Default poll 1.0s, 4 consecutive identical snapshots, min length 1.
  - Generation is incomplete while Stop is visible, Send is disabled, or a
    typing/thinking indicator is visible.
  - A candidate is accepted only when it is a *new* response vs baseline,
    meets min length, is stable for N checks, and generation is complete.
  - `timeout_sec` is a **hard cutoff** (issue #372): overrunning it without
    a terminal event raises `ResponseDetectionTimeoutError` (the dispatch
    loop in the Agent layer retries per `MAX_ATTEMPTS`). The 30s periodic
    cloud reload sync is recovery inside the budget, never a cutoff reset.
  - The 30s periodic cloud reload fires only when there is **no forward
    progress** — the committed response text is unchanged since the last reload
    (issue #382). Reloading mid-stream would reset the stability counter and
    could starve a long generation out of the stability condition, so a stream
    whose text keeps growing across the window suppresses the reload entirely.
  - The `safety_timeout_sec` circuit breaker is the absolute backstop for
    pathological loops; it defaults to 4h and is operator-tunable via the
    `QWEN_STREAM_SAFETY_TIMEOUT_SEC` environment variable (issue #330).
  - Stall detection is event-driven: no forward lifecycle event (thinking,
    streamed text change, completion) for `stall_timeout_sec` (default
    300s) raises `StuckDetectedError`; slow-but-alive generations are never
    misclassified while text keeps changing.
  - `validate_response_content` rejects empty text and challenge keywords
    (`just a moment`, `verify you are human`, 502/504, upload-still-parsing,
    etc.). CAPTCHA phrases become `AuthRequiredError`.
  - Poll cycle must stay under 300ms of blocking work (NFR).
- **Edge Cases**: network drop mid-stream; UI noise ("Qwen3" tags); response
  shorter than min length; hard cutoff mid-stream; Playwright IPC death;
  long streaming generation still growing when the 30s reload window elapses
  (reload suppressed, stability counter preserved).
- **Error Handling**:
  - `ResponseDetectionTimeoutError` on `timeout_sec` hard cutoff and on the
    safety circuit breaker (propagated for orchestrator retry).
  - `StuckDetectedError` on event-driven stall (retryable).
  - Transient Playwright `TimeoutError` / `Error` trigger reload-based
    recovery without failing the wait.
  - `OutputValidationError` / `AuthRequiredError` from content validation
    (propagated, not swallowed).
- **Acceptance Criteria**:
  - [ ]  Wait is blocked when `dispatch_acknowledged` is false.
  - [ ]  Stable new text + complete generation returns `ResponseText`.
  - [ ]  CAPTCHA keyword in a short page raises `AuthRequiredError`.
  - [ ]  Server-error keyword raises `OutputValidationError`.
  - [ ]  `timeout_sec` budget overrun raises `ResponseDetectionTimeoutError`.
- **Tests**: `tests/unit_capability_stream_monitor.py`,
  `tests/unit_capability_stream_resilience.py`, `tests/contract_qwen_auto.py`.

### FR-007: Workspace Provisioner

- **Capability**: `capabilities_workspace_provisioner.py` → `WorkspaceProvisioner`
- **Contract**: `IWorkspaceProtocol`
- **Description**: Create a first-run project workspace: XDG data dirs,
  `.agents/skills/qwen-web/SKILL.md`, `.qwen-web/` symlinks, and a
  `.gitignore` entry.
- **Input**: `FilePath` target directory.
- **Output**: Directories, skill file, symlinks, and gitignore mutation.
  No return value.
- **Business Rules**:
  - Always ensure XDG `DEFAULT_JOBS_DIR`, `DEFAULT_OUTPUT`, and `DEFAULT_LOG`
    exist.
  - Copy `SKILL.md` from XDG copy if present, else package root, else write
    a minimal front-matter stub.
  - Create five `.qwen-web/` directory symlinks into the XDG paths
    (issue #319 — the spec previously listed only three, and named an `input`
    link the provisioner never creates):

    | Link | Target |
    |---|---|
    | `.qwen-web/jobs` | `DEFAULT_JOBS_DIR` |
    | `.qwen-web/log` | `DEFAULT_LOG` |
    | `.qwen-web/output` | `DEFAULT_OUTPUT` |
    | `.qwen-web/qwen_session` | `DEFAULT_SESSION` |
    | `.qwen-web/swarm` | `SWARM_OUTPUT_ROOT` |

    An existing real directory occupying a link name is moved aside to
    `<name>.backup-<ns>` rather than clobbered; broken or stale links are
    replaced. A target that cannot be linked (restricted filesystem) is
    created as a real directory so `init` still succeeds.
  - Append `.qwen-web/` to `.gitignore` if missing; create the file when
    absent. Symlink creation `OSError` is ignored (non-fatal).
- **Edge Cases**: target is not a git repo; `.gitignore` exists without
  trailing newline; symlink not permitted (some FS); XDG and package skill
  files both missing; a pre-existing real directory occupying a link name.
- **Error Handling**: filesystem errors on skill write propagate. Symlink
  failures are skipped so `init` still succeeds on restricted hosts.
- **Acceptance Criteria**:
  - [ ]  `init` creates `.agents/skills/qwen-web/SKILL.md`.
  - [ ]  All five links (`jobs`, `log`, `output`, `qwen_session`, `swarm`)
    resolve to their documented XDG targets when linking works.
  - [ ]  `.gitignore` contains `.qwen-web/` exactly once after repeated inits.
  - [ ]  XDG jobs/output/log directories exist after init.
  - [ ]  A second `init` leaves the link set unchanged (idempotent).
- **Tests**: `tests/integration_surface_init_cmd.py`.

### FR-008: Observability Setup

- **Capability**: `capabilities_observability_setup.py` → `ObservabilitySetup`
- **Contract**: `IObservabilityProtocol`
- **Description**: Bootstrap the telemetry stack (Sentry → OpenTelemetry →
  structlog) and process-wide exception hooks. In-memory metrics
  (`MetricsCounter`) and `status.json` (`StatusFileWriter`) are helper types
  in this file — not standalone capabilities. The legacy `IMetricsProtocol`
  and `IStatusProtocol` contracts remain helper-level compatibility contracts
  owned by this FR-008; they do not represent additional FRs or capabilities.
- **Input**: log `Path`; env `SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
  `OTEL_SERVICE_NAME`, `ENVIRONMENT`.
- **Output**: configured loggers (`stderr` + `app.jsonl`), optional OTLP
  tracer, optional Sentry client, installed `sys`/`threading` excepthooks.
- **Business Rules**:
  - Missing optional packages or empty DSN/endpoint must no-op (graceful
    degradation). Never fail process start because telemetry is absent.
  - TTY or `ENVIRONMENT=development` uses colored console renderer; else
    JSON lines.
  - Every log event may carry active `trace_id` / `span_id`.
  - `bind_run_context` / `clear_run_context` scope `run_id` via contextvars.
  - Unhandled exceptions are logged as `unhandled_exception` with
    `ErrorCategory`, captured by Sentry when available.
  - `KeyboardInterrupt` exits 130. Other unhandled exits 1.
  - `exit_code_for` maps domain errors to process codes for surfaces.
- **Edge Cases**: import of sentry/otel/structlog fails; log dir not
  writable (file handler skipped); no active span; hook installed twice.
- **Error Handling**: all third-party init is wrapped in `suppress` /
  `ImportError` guards. File handler `OSError` is ignored.
- **Update rollback outcomes (issue #279)**: `UpdateReport.rollback_status`
  disambiguates what a failed update did with the previous version:
  - [ ]  **Full rollback** (`rollback_status="full"`): package and browser
    both restored to the previous version; `rolled_back=True`.
  - [ ]  **Partial rollback** (`rollback_status="partial"`): package
    restored but browser sync failed (or vice versa); `rolled_back=True`
    and the report message ends with `Partial rollback: package restored
    but browser sync failed. Run `qwen-web-arwaky update --force` to retry
    browser sync.`
  - [ ]  **Skipped rollback** (`rollback_status="skipped"`): the previous
    version is unknown, or an editable install was detected;
    `rolled_back=False` and the step detail says exactly how to recover
    (`git checkout` for editable installs, manual `pip install` otherwise).
  - [ ]  No rollback needed (`rollback_status="none"`): the update was
    healthy; `rolled_back=False`.
- **Acceptance Criteria**:
  - [ ]  `setup_observability` succeeds with no Sentry/OTel installed.
  - [ ]  JSON renderer is used when stderr is not a TTY and env is production.
  - [ ]  Excepthook logs critical + exits 1 for a generic exception.
  - [ ]  KeyboardInterrupt path exits 130.
  - [ ]  `start_span` is a no-op context manager when OTel is missing.
- **Tests**: `tests/unit_observability_stderr.py`,
  `tests/unit_structlog_no_percent_interp.py`.

## Capability Inventory

The product requirement inventory is 13 capabilities (one per P0 capability,
FR-001…FR-013 in `PRD.md`). FR-001…FR-008 are the browser-automation
capabilities documented above; FR-009…FR-013 are the extended Core
capabilities (folder compiler, folder-to-attachment adapter, job manager,
TUI slot configuration, update manager) whose traceability rows are listed
below. The old heading “exactly 8” was an inventory error.

Metrics counters and `status.json` writes are helper types inside
`capabilities_observability_setup.py` (FR-008). Do not reintroduce them as
standalone capability files.

## API Contract

There is no single `ICoreAggregate` facade (the old heading referred to a
non-existent `CoreOrchestrator` API — issue #378). The surface-facing API is
a set of small, purpose-focused aggregate contracts declared in
`modules/shared/src/contract_core_aggregate.py`, each implemented by an
agent-layer orchestrator (`agent_*_orchestrator.py`) and composed by
`root_core_container.SharedContainer`. Each aggregate sequences the FR
capabilities it needs; no aggregate re-implements capability business rules.

| Aggregate contract | Implementation | Operations (key) |
| -------------------- | ---------------- | ------------------ |
| `IPromptFlowAggregate` | `agent_shared_flow_orchestrator.py` → `SharedFlowOrchestrator` | `dispatch_and_wait_for_response` (inject → send → wait, FR-004/005/006) |
| `IDirectPromptAggregate` | `agent_direct_prompt_orchestrator.py` → `DirectPromptOrchestrator` | `process_direct_prompt` (inline text) |
| `IPromptFileAggregate` | `agent_prompt_file_orchestrator.py` → `PromptFileOrchestrator` | `process_prompt_file_only` (+ contract `request_cancel`, issue #360) |
| `IAttachmentPromptAggregate` | `agent_attachment_prompt_orchestrator.py` → `AttachmentPromptOrchestrator` | `process_prompt_with_attachment` (+ contract `request_cancel`, issue #360) |
| `ISessionAggregate` | `agent_session_orchestrator.py` → `SessionOrchestrator` | `validate_session`, `delete_session` (FR-001) |
| `ISetupAggregate` | `agent_setup_orchestrator.py` → `SetupOrchestrator` | `setup_session` (interactive login) |
| `IJobManagerAggregate` | `agent_job_orchestrator.py` → `AgentJobOrchestrator` | `submit_file_job`, `submit_attachment_job`, `get_job_status`, `list_jobs`, `shutdown` (FR-011) |

The Swarm orchestrator (`agent_swarm_orchestrator.py`) implements
`ISwarmAggregate` from `modules/shared/src/contract_swarm_aggregate.py`
(see “Swarm Orchestrator (CR-2026-004)” below) and composes
`IAttachmentPromptAggregate` per agent — it is an aggregate consumer, not a
capability of its own.

## Swarm Orchestrator (CR-2026-004)

The Swarm feature is approved product scope under change request CR-2026-004
(see `PRD.md` Scope); this section is its FRD entry (issue #313).

- **Aggregate**: `agent_swarm_orchestrator.py` → `SwarmOrchestrator`
- **Contract**: `ISwarmAggregate` (`start`, `snapshot`, `cancel` in
  `contract_swarm_aggregate.py`)
- **Description**: Fan out every discovered role template
  (`modules/templates/*.md`) as one agent over a shared attachment (file or
  folder, the latter compiled via FR-009/FR-010), with bounded browser
  concurrency and per-agent retry.
- **Input**: `input_path` (file or folder), optional `output_root`,
  `browser_concurrency` (default `DEFAULT_MAX_WORKERS`, hard-capped at 10),
  `max_attempts` (default `MAX_ATTEMPTS`).
- **Output**: immutable `SwarmSnapshot` reads (`queued → running →
  completed|partial|failed|cancelled`), per-agent `SwarmAgentSnapshot`, and a
  `manifest.json` rewritten on every transition under the swarm root.
- **Business Rules**:
  - One browser per active agent, never more than `browser_concurrency`.
  - A retryable failure (rate limit, timeout/timed out, connection/network,
    empty, stuck) is retried up to `max_attempts`; a non-retryable error
    fails that agent immediately without touching siblings.
  - **Resource governance (issue #277)**: the Swarm must never bypass the
    shared guards. `SharedContainer` injects its `CircuitBreaker` and
    `RateLimiter` into the orchestrator; before each agent attempt the
    breaker is checked (a tripped breaker fails that agent only, siblings
    keep their in-flight browsers) and a rate-limit slot is acquired
    (a busy slot waits for the reported backoff, which the user can still
    cancel). **Maximum concurrent browsers per Swarm = min(DEFAULT_MAX_WORKERS,
    available_system_memory / 512 MB)**, hard-capped at 10. A Swarm with
    4+ concurrent browsers surfaces the TUI warning
    `"This will launch up to N browser processes. Continue?"` via
    `SwarmOrchestrator.resource_warning`, shown through a `ConfirmModal`
    before the fan-out starts.
  - Cancellation is per-agent via `threading.Event` passed as
    `cancel_event` into `IAttachmentPromptAggregate`: cancelling the swarm
    sets every agent event and calls the contract-level `request_cancel`
    (issue #360), closing only in-flight browser contexts.
  - Session expiry containment (issue #275): an expiring session surfaces as
    a per-agent `AUTH_REQUIRED` failure for that agent only; sibling agents
    keep their in-flight browsers; the swarm finishes as `partial`/`failed`
    rather than aborting the whole fan-out. Recovery is re-login, then
    re-run the swarm.
- **Edge Cases**: empty template set (refused at start), input folder
  without compilable files, cancel before first attempt, executor shutdown
  while snapshots stream.
- **Error Handling**: per-agent error recorded on the snapshot
  (`error` field); swarm-level failures raise before the fan-out starts.
- **Tests**: `tests/unit_agent_swarm_orchestrator.py` (discovery/format,
  transient retry → partial, stuck retry, non-retryable → failed).

## Integration Points

- **3rd Party**: Playwright Chromium, tenacity, structlog, OpenTelemetry OTLP
  HTTP, Sentry SDK.
- **Internal**: `modules/shared` taxonomy VOs, domain errors, contracts,
  path/prompt/validation utilities. Surfaces (`modules/cli`, `modules/mcp`)
  consume only the aggregate contracts from
  `modules/shared/src/contract_core_aggregate.py` (plus `ISwarmAggregate`
  for the TUI swarm tab).
- **DI**: `root_core_container.SharedContainer` wires all capabilities and
  agent orchestrators.

## Traceability (FR → Code → Tests)


| FR     | Protocol                 | Capability                              | Tests |
| -------- | -------------------------- | ----------------------------------------- | ------- |
| FR-001 | `IBrowserProtocol`       | `capabilities_browser_adapter.py`       | `unit_browser_adapter.py`, `integration_browser_session.py` |
| FR-002 | `IUploadProtocol`        | `capabilities_file_uploader.py`         | `unit_capability_file_uploader.py` |
| FR-003 | `ISaverProtocol`         | `capabilities_output_saver.py`          | `unit_capability_output_saver.py` |
| FR-004 | `IInjectionProtocol`     | `capabilities_prompt_injector.py`       | `unit_capability_prompt_injector.py`, `unit_capability_prompt_injector_verify.py` |
| FR-005 | `ISendProtocol`          | `capabilities_send_dispatcher.py`       | `unit_capability_send_dispatcher.py` |
| FR-006 | `IStreamProtocol`        | `capabilities_stream_monitor.py`        | `unit_capability_stream_monitor.py`, `unit_capability_stream_resilience.py` |
| FR-007 | `IWorkspaceProtocol`     | `capabilities_workspace_provisioner.py` | `integration_surface_init_cmd.py` |
| FR-008 | `IObservabilityProtocol` | `capabilities_observability_setup.py`   | `unit_observability_stderr.py`, `unit_structlog_no_percent_interp.py` |
| FR-009 | `IFolderCompileProtocol` | `capabilities_folder_compiler.py`       | `unit_folder_compiler.py` |
| FR-010 | `IFolderToAttachmentProtocol` | `capabilities_folder_to_attachment.py` | `unit_folder_compiler.py` (adapter paths) |
| FR-011 | `IJobStorageProtocol`    | `capabilities_job_manager.py`           | `unit_capability_job_manager.py`, `integration_parallel_jobs.py` |
| FR-012 | `ITuiSlotConfigProtocol` | `capabilities_tui_slot_config.py`       | `unit_surface_cli_tui_app.py` (slot planning) |
| FR-013 | `IUpdateProtocol`        | `capabilities_update_manager.py`        | `unit_surface_cli_update_command.py` |
| CR-2026-004 | `ISwarmAggregate`    | `agent_swarm_orchestrator.py`           | `unit_agent_swarm_orchestrator.py` |

End-to-end locks: `tests/contract_qwen_auto.py` (behavior lock),
`tests/integration_surface_cli_main.py`, `tests/integration_surface_mcp.py` (surface
integration).

## Non-functional Requirements (Detailed)

- **Performance**: DOM poll work < 300 ms/cycle. Asset blocking must cut
  image/font/media traffic on non-login runs. Launch retry budget is 3 × 2s.
- **Security**: session dir `0o700`; no credentials in stdout/JSONL; scraped
  model text is untrusted data (never agent instructions).
- **Reliability**: atomic output writes; upload degrades to text-only;
  telemetry is best-effort.
- **Maintainability**: capabilities implement protocols only; no
  inter-capability imports; agent depends on contracts.

## Test Scenarios / QA Checklist

- [ ]  FR-001: expired cookies raise `AuthRequiredError` and point the user
  at `qwen-web-arwaky login`.
- [ ]  FR-002: attach card appears on fixture; oversized file never opens chooser.
- [ ]  FR-003: killing the process during write leaves no half file (atomic).
- [ ]  FR-004: 100k-char prompt injects via React setter on fixture.
- [ ]  FR-005: send is refused while attachment parse gate is false.
- [ ]  FR-006: circuit of Stop button → streaming text → stable text completes.
- [ ]  FR-007: second `init` is idempotent and all five `.qwen-web` links
  resolve to their XDG targets.
- [ ]  FR-008: process starts with empty `SENTRY_DSN` and no OTLP endpoint.
- [ ]  Pipeline smoke test (issue #322): `qwen-web-arwaky doctor --smoke`
  reports a pass/fail result for a headless browser round-trip against the
  saved session. The browser launch is live and gated on an authenticated
  session, so CI asserts the deterministic wiring — that the flag reaches the
  surface, appends the sixth check, and maps the aggregate result to
  pass/fail — while the operator runs the full round-trip.
  Locks: `modules/cli/tests/integration_doctor_smoke.py`.
- [ ]  Aggregate boundary: failed single-file prompts return an error envelope,
  nested role routing is preserved, and a
  supplied `AppConfig` reaches the browser session unchanged. Input files stay
  in place; status is represented by the error envelope and logs.

## Assumptions & Constraints

- Linux host with a Chromium/Chrome binary (Playwright or system).
- Valid session is created once via headed `--login` (CAPTCHA cannot be
  solved headless).
- Playwright sync API requires a dedicated thread event loop (FR-001
  isolates it).
- `chat.qwen.ai` DOM will drift; selectors are multi-tier and locked by
  `tests/fixtures/qwen_fixture.html`.

## Glossary

- **AES**: Agentic Engineering System (7-layer architecture).
- **XDG**: Base Directory spec used for input/output/log/session paths.
- **Persistent context**: Chromium user-data dir that keeps cookies/LocalStorage.
- **Stability check**: N consecutive identical response snapshots plus
  generation-complete UI.

## Reference

- PRD: [Root PRD.md](../../PRD.md)
- Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
- Behavior lock: [TEST.md](../../TEST.md)
