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
- **Edge Cases**: stale profile after crash; missing execute bit on an
  existing session dir; concurrent Chromium instances; headed login vs
  headless batch; user closes the page mid-navigation; load-state wait times
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
- **Tests**: `tests/test_browser.py`, `tests/test_browser_extended.py`,
  `tests/test_browser_session.py`, `tests/test_login_session.py`.

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
- **Tests**: `tests/test_file_uploader.py`, `tests/test_qwen_client_behavior.py`.

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
- **Tests**: `tests/test_saver.py`, `tests/test_saver_extended.py`.

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
- **Tests**: `tests/test_prompt_injector.py`,
  `tests/test_prompt_injector_extended.py`,
  `tests/test_prompt_injector_final.py`, `tests/test_qwen_client_behavior.py`.

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
- **Tests**: `tests/test_sender.py`, `tests/test_sender_extended.py`,
  `tests/test_qwen_client_behavior.py`.

### FR-006: Stream Monitor

- **Capability**: `capabilities_stream_monitor.py` → `StreamMonitor`
- **Contract**: `IStreamProtocol`
- **Description**: Poll the DOM until the assistant response is stable and
  generation UI (Stop / disabled Send / typing) has cleared, then validate
  the text is not a CAPTCHA or error page.
- **Input**: `Page`, `timeout_sec`, `msg_count_before`, `LifecycleEmitter`,
  poll/stability/min-length knobs, `dispatch_acknowledged` gate.
- **Output**: `ResponseText` or `None` on hard timeout with no text.
  Events: `EVENT_THINKING_STARTED`, `EVENT_STREAMING_GENERATION`,
  `EVENT_GENERATION_FINISHED`.
- **Business Rules**:
  - Must refuse wait when `dispatch_acknowledged` is false.
  - Default poll 1.0s, 4 consecutive identical snapshots, min length 1.
  - Generation is incomplete while Stop is visible, Send is disabled, or a
    typing/thinking indicator is visible.
  - A candidate is accepted only when it is a *new* response vs baseline,
    meets min length, is stable for N checks, and generation is complete
    (or timeout returns last non-empty text after validation).
  - `validate_response_content` rejects empty text and challenge keywords
    (`just a moment`, `verify you are human`, 502/504, upload-still-parsing,
    etc.). CAPTCHA phrases become `AuthRequiredError`.
  - Poll cycle must stay under 300ms of blocking work (NFR).
- **Edge Cases**: network drop mid-stream; UI noise ("Qwen3" tags); response
  shorter than min length; timeout with partial text; timeout with no text;
  Playwright IPC death.
- **Error Handling**:
  - `NetworkTimeoutError` on Playwright timeout / IPC `Error`.
  - `OutputValidationError` / `AuthRequiredError` from content validation
    (propagated, not swallowed).
  - Unexpected exceptions are logged and re-raised.
- **Acceptance Criteria**:
  - [ ]  Wait is blocked when `dispatch_acknowledged` is false.
  - [ ]  Stable new text + complete generation returns `ResponseText`.
  - [ ]  CAPTCHA keyword in a short page raises `AuthRequiredError`.
  - [ ]  Server-error keyword raises `OutputValidationError`.
  - [ ]  Hard timeout with no text returns `None`.
- **Tests**: `tests/test_streamer.py`, `tests/test_streamer_extended.py`,
  `tests/test_qwen_client_behavior.py`.

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
  - Always ensure XDG `DEFAULT_TODO`, `DEFAULT_OUTPUT`, `DEFAULT_LOG`.
  - Copy `SKILL.md` from XDG copy if present, else package root, else write
    a minimal front-matter stub.
  - Create `.qwen-web/{log,input,output}` as directory symlinks to the XDG
    paths. Existing real directories are left untouched. Broken/old links
    are replaced.
  - Append `.qwen-web/` to `.gitignore` if missing; create the file when
    absent. Symlink creation `OSError` is ignored (non-fatal).
- **Edge Cases**: target is not a git repo; `.gitignore` exists without
  trailing newline; symlink not permitted (some FS); XDG and package skill
  files both missing.
- **Error Handling**: filesystem errors on skill write propagate. Symlink
  failures are skipped so `init` still succeeds on restricted hosts.
- **Acceptance Criteria**:
  - [ ]  `init` creates `.agents/skills/qwen-web/SKILL.md`.
  - [ ]  `.qwen-web/input|output|log` point at XDG defaults when linking works.
  - [ ]  `.gitignore` contains `.qwen-web/` exactly once after repeated inits.
  - [ ]  XDG input/output/log directories exist after init.
- **Tests**: `tests/test_init_cmd.py`.

### FR-008: Observability Setup

- **Capability**: `capabilities_observability_setup.py` → `ObservabilitySetup`
- **Contract**: `IObservabilityProtocol`
- **Description**: Bootstrap the telemetry stack (Sentry → OpenTelemetry →
  structlog) and process-wide exception hooks. In-memory metrics
  (`MetricsCounter`) and `status.json` (`StatusFileWriter`) are helper types
  in this file — not standalone capabilities. The legacy `IMetricsProtocol`
  and `IStatusProtocol` contracts remain helper-level compatibility contracts
  owned by FR-009; they do not represent additional FRs or capabilities.
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
- **Acceptance Criteria**:
  - [ ]  `setup_observability` succeeds with no Sentry/OTel installed.
  - [ ]  JSON renderer is used when stderr is not a TTY and env is production.
  - [ ]  Excepthook logs critical + exits 1 for a generic exception.
  - [ ]  KeyboardInterrupt path exits 130.
  - [ ]  `start_span` is a no-op context manager when OTel is missing.
- **Tests**: `tests/test_observability.py`, `tests/test_observability_extended.py`.

## Capability Inventory (exactly 8)

Metrics counters and `status.json` writes are helper types inside
`capabilities_observability_setup.py` (FR-009). Do not reintroduce them as
standalone capability files.

## API Contract

`ICoreAggregate` (implemented by `CoreOrchestrator`) is the surface-facing
API. It sequences FR-001…FR-008; it does not implement their business rules.


| Operation             | Input                                        | Output         | Description                                          |
| ----------------------- | ---------------------------------------------- | ---------------- | ------------------------------------------------------ |
| `process_single_file` | `input_file`, `output_file`, `headless`      | `ResponseText` | One file: attach → inject → send → save → audit. |
| `process_batch`       | `input_dir`, `output_dir`, `headless`        | `ResponseText` | All processable files; per-file isolation.           |
| `process_watcher`     | `interval_sec`, `headless`                   | `ResponseText` | Poll input dir until SIGINT/SIGTERM.                 |
| `process_mode`        | `AppConfig`                                  | `ResponseText` | Dispatch watcher / single / batch.                   |
| `send_prompt`         | `prompt`, `timeout_sec`, `headless`          | `ResponseText` | Raw text without durable file routing.               |
| `setup_session`       | confirmation callback, optional session path | `ResponseText` | Validate saved session or headed login.              |
| `init_workspace`      | `target_dir`                                 | `None`         | Provision skill + XDG links (FR-007).                |

## Integration Points

- **3rd Party**: Playwright Chromium, tenacity, structlog, OpenTelemetry OTLP
  HTTP, Sentry SDK.
- **Internal**: `modules/shared` taxonomy VOs, domain errors, contracts,
  path/prompt/validation utilities. Surfaces (`modules/cli`, `modules/mcp`)
  consume only `ICoreAggregate`.
- **DI**: `root_core_container.SharedContainer` wires all eight capabilities.

## Traceability (FR → Code → Tests)


| FR     | Protocol                 | Capability                              |
| -------- | -------------------------- | ----------------------------------------- |
| FR-001 | `IBrowserProtocol`       | `capabilities_browser_adapter.py`       |
| FR-002 | `IUploadProtocol`        | `capabilities_file_uploader.py`         |
| FR-003 | `ISaverProtocol`         | `capabilities_output_saver.py`          |
| FR-004 | `IInjectionProtocol`     | `capabilities_prompt_injector.py`       |
| FR-005 | `ISendProtocol`          | `capabilities_send_dispatcher.py`       |
| FR-006 | `IStreamProtocol`        | `capabilities_stream_monitor.py`        |
| FR-007 | `IWorkspaceProtocol`     | `capabilities_workspace_provisioner.py` |
| FR-008 | `IObservabilityProtocol` | `capabilities_observability_setup.py`   |

End-to-end locks: `tests/test_qwen_client_behavior.py`, `tests/test_e2e_pipeline.py` (manual/`e2e` mark).

## Non-functional Requirements (Detailed)

- **Performance**: DOM poll work < 300 ms/cycle. Asset blocking must cut
  image/font/media traffic on non-login runs. Launch retry budget is 3 × 2s.
- **Security**: session dir `0o700`; no credentials in stdout/JSONL; scraped
  model text is untrusted data (never agent instructions).
- **Reliability**: atomic output writes; upload degrades to text-only;
  telemetry is best-effort; watcher answers SIGINT/SIGTERM within ~1s sleep
  chunk.
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
- [ ]  FR-007: second `init` is idempotent.
- [ ]  FR-008: process starts with empty `SENTRY_DSN` and no OTLP endpoint.
- [ ]  Aggregate boundary: failed batch items report `Failed: 1`, failed single
  files return an error envelope, nested role routing is preserved, and a
  supplied `AppConfig` reaches the browser session unchanged.

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
- **Quarantine**: agent move of a failed file to `failed/` (orchestration,
  not a capability FR).

## Reference

- PRD: [Root PRD.md](../../PRD.md)
- Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
- Behavior lock: [TEST.md](../../TEST.md)
