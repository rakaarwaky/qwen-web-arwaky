# TEST.md — Behavior Regression Lock & TDD Workflow

> **Purpose:** Lock the exact DOM selectors, JS injection strategies, and
> response-detection behavior against the verified live Qwen UI (Qwen3.8-Max,
> August 2026). When adding features later, these tests fail first if old
> behavior silently regresses.

---

## 1. What Is Locked

The regression suite exercises the **production methods directly** against a
real headless Chromium + a local HTML fixture (`tests/fixtures/qwen_fixture.html`)
that mirrors the exact DOM structure verified live on `chat.qwen.ai`.

### Locked modules & their verified behaviors

| Module | Method | Verified behavior | Source of truth |
|--------|--------|-------------------|-----------------|
| `core/src/capabilities_prompt_injector.py` | `find_input` | Matches `textarea.message-input-textarea` | Live probe 2026-08-09 |
| `core/src/capabilities_prompt_injector.py` | `inject_text` | Tier 1: React `HTMLTextAreaElement.prototype` setter; Tier 2: clipboard paste; Tier 3: `fill()`/`type()` | Live probe 2026-08-09 |
| `core/src/capabilities_file_uploader.py` | `upload_attachment` | `.mode-select-open` → `Upload attachment` → file chooser → `.message-input-column-file` card | Live probe 2026-08-09 |
| `core/src/capabilities_file_uploader.py` | `validate_file` | Rejects oversized files before the chooser opens | Live probe 2026-08-09 |
| `core/src/capabilities_send_dispatcher.py` | `click_send` | Clicks `button[aria-label*='Send']`; Enter fallback | Live probe 2026-08-09 |
| `core/src/capabilities_send_dispatcher.py` | `count_messages` | Counts `.markdown-body` nodes under `#chatLog` | Live probe 2026-08-09 |
| `core/src/capabilities_send_dispatcher.py` | `latest_message_text` | Returns `.markdown-body` text of last assistant node | Live probe 2026-08-09 |
| `shared/src/utility_core_validation.py` | `validate_response_content` | Detects CAPTCHA challenges, server error pages, empty responses | Live probe 2026-08-09 |
| `core/src/capabilities_stream_monitor.py` | `wait_for_response` | Stability loop with output validation | Live probe 2026-08-09 |
| `core/src/capabilities_stream_monitor.py` | `is_thinking_active` | Visible thinking card without a completed marker counts as active | Live probe 2026-08-09 |
| `core/src/capabilities_browser_adapter.py` | `SessionCheck.is_alive` | Verifies page readiness and textarea presence | Live probe 2026-08-09 |
| `core/src/capabilities_browser_adapter.py` | `SessionCheck.check_auth` | Detects login redirects and missing textarea | Live probe 2026-08-09 |
| `core/src/agent_attachment_prompt_orchestrator.py` | `process_prompt_with_attachment` | Full pipeline: new chat → attach → inject → parse wait → send → response | Live probe 2026-08-09 |
| `core/src/agent_prompt_file_orchestrator.py` | `process_prompt_file_only` | Same pipeline without attachment | Live probe 2026-08-09 |

> Paths are relative to `modules/`. Method names in this table must always
> resolve against the current tree — if a rename lands, update this table in the
> same commit.

### Dead code removed (verified 2026-08-09)

| Removed strategy | Reason |
|------------------|--------|
| `#filesUpload` `set_input_files` | Hidden input; UI no longer processes file uploads via this path |
| `[aria-label*='Upload']` button click | Button no longer has upload aria-label |
| `new DataTransfer(...)` JS injection | Depended on `#filesUpload` which is dead |
| `fill()` / `type()` for primary injection | Fragile in React; replaced with React-setter + clipboard |

---

## 2. Fixture Design: 1:1 With Production Runtime

### Browser fixture (`qwen_fixture.html`)
Mirrors the **exact CSS selectors** the production code uses. If Qwen changes
a class name or DOM structure, tests fail **before** production breaks in the
field.

Key elements mirrored:
- `textarea.message-input-textarea` (id `chatInput`)
- `.mode-select-open` → `.mode-select-dropdown-item` (Upload attachment)
- `.message-input-column-file` (attachment card, `.fileitem-file-size` status)
- `button[aria-label*='Send']` (id `sendBtn`)
- `#chatLog` with `.markdown-body` assistant messages
- `.ant-message-error` / `.ant-message-warning` (error toasts)
- `.spinner` / `.thinking` (parsing indicators)

### Pipeline fixtures (`tests/fixtures/input|output|log/`)
These are **production-mirrored runtime directories** (1:1 with `input/`,
`output/`, `log/`). Golden task content is pinned in `conftest.py`
`_GOLDEN_TASKS` and restored by `reset_fixture_state` before every test.

Role fixtures (real source-review prompts, **not** injection payloads):
- `role-architect/todo/task_001.md` — auth module layer-boundary review
- `role-business-analyst/todo/task_001.md` — payment feature user-story gap analysis
- `role-tech-lead/todo/task_001.md` — LRU cache implementation PR review

---

## 3. Running the Tests

```bash
# Full suite (behavior + pipeline)
pytest tests/ -v

# Behavior lock only (fast, ~90s headless)
pytest tests/unit_browser_adapter.py -v

# With coverage
pytest tests/unit_browser_adapter.py --cov=modules --cov-report=term-missing
```

### Expected coverage boundary

Measured with `pytest tests/ --cov=modules` (2026-09-22, 46 test files):
**total line coverage ≈ 75%** of `modules/`. The historical "<40% with four
layers at 0%" estimate (issue #339) does not hold against measurement — no
module layer sits at 0%. Representative numbers:

| Module / layer | Measured | Notes |
|----------------|----------|-------|
| Total `modules/` | **75%** | Steady-state target for PRs: do not regress |
| Shared contract/taxonomy layer | 93–100% | Contracts & constants — fully locked |
| `capabilities_stream_monitor.py` | ~89% | Uncovered: live IPC recovery branches |
| `capabilities_prompt_injector.py` | ~95% | Uncovered: error branches, clipboard fallback edges |
| `capabilities_send_dispatcher.py` | ~80% | Uncovered: PlaywrightError fallback branches |
| `capabilities_update_manager.py` | ~62% | Uncovered: real pip/git subprocess paths (mocked in unit tests) |
| `agent_swarm_orchestrator.py` | ~76% | Uncovered: shutdown/executor races |
| `agent_shared_flow_orchestrator.py` | ~29% | Lowest agent layer — dispatch retry matrix needs browser fakes |
| TUI surface (`surface_cli_tui_*`) | 38–100% | Handlers/workers below compose/app — see strategy §7.5 |
| MCP surface | ~70% | Tool handlers covered via `unit_mcp_hardening.py` |

The uncovered percentages are `except PlaywrightError`, `start_new_chat`
network redirects, `_wait_for_auth` login detection, real subprocess
executions, and other error-handling branches that require live
network/auth — validated manually (see §5 Manual Probe).

---

## 4. TDD Workflow: Adding Features Without Breaking Old Behavior

### Step-by-step

1. **Run the lock first** (red baseline — should all pass before you change anything):
   ```bash
   pytest tests/unit_browser_adapter.py -v
   ```

2. **Write a failing test for the new feature** against `qwen_fixture.html`.
   Add elements/states to the fixture if needed.

3. **Implement the feature** in the appropriate module.

4. **Run the lock again**:
   - If old tests fail → you broke existing behavior. Fix before merging.
   - If only the new test passes → green, safe to commit.

5. **If Qwen UI changes** (selector drift):
   - Update `qwen_fixture.html` to match the new DOM
   - Update `modules/shared/src/taxonomy_core_constant.py` selectors (if centralized)
   - Update the affected test(s)
   - Do NOT skip the test — that's how drift goes undetected.

### Golden rule

> **The fixture is the single source of truth for DOM structure.**
> If a selector in production code doesn't work against `qwen_fixture.html`,
> it doesn't work in production either. Fix the fixture + selector together,
> never independently.

---

## 5. Manual Probe (Headed) — Ad-Hoc Verification

For debugging live UI changes without committing fixture changes:

```bash
export DISPLAY=:0
python3 tests/manual_probe.py
```

This opens a visible browser window against `chat.qwen.ai` (using your saved
session in `qwen_session/`) and exercises the real upload + inject + send flow.
Screenshots saved to `tests/artifacts/`.

Do NOT use `manual_probe.py` as a CI test — it requires a saved login session
and a real display.

---

## 6. Troubleshooting

### "Upload attachment" fails in tests
- Check `.mode-select-open` exists in `qwen_fixture.html`
- Check `.mode-select-dropdown-item` has text "Upload attachment"
- The test must `expect_file_chooser` **before** clicking the dropdown item

### Send button not enabled
- `_wait_for_input_parsed` requires `.fileitem-file-size` status text to not
  contain "Parsing" and `sendBtn` to be `!disabled` and `offsetWidth > 0`
- In the fixture, set `attachmentCard.classList.add('visible')` before asserting

### Clipboard fallback test flaky in headless
- The test stubs `navigator.clipboard.writeText` and simulates paste via JS —
  it does **not** depend on OS clipboard availability
- If you change the clipboard tier logic, update the stub in the test too

### E2E tests need internet + session
- `test_e2e_pipeline.py` is marked `@pytest.mark.e2e` and excluded from CI by default
- Run with: `pytest tests/integration_browser_session.py -m e2e`
- Requires `qwen_session/Default` to exist (valid saved login)

---

## 7. File Inventory

```
tests/
├── conftest.py                          # Golden-task fixtures + browser/behavior fixtures
├── fixtures/
│   ├── qwen_fixture.html                # DOM mirror for behavior tests
│   ├── input/                           # 1:1 production mirror (real task prompts)
│   ├── output/
│   └── log/
├── contract_qwen_auto.py                # Behavior-lock tests (TDD safety net)
├── pipeline_fixtures.py                 # Fixture state management tests
├── unit_concurrency_guards.py           # Thread-safety locks for breaker/limiter/jobs
├── unit_mcp_hardening.py                # MCP registry + workspace path safety
└── manual_probe.py                      # Ad-hoc headed probe for live UI debugging
modules/
├── shared/src/taxonomy_core_constant.py  # Selectors & constants
├── core/src/capabilities_prompt_injector.py
├── core/src/capabilities_send_dispatcher.py
├── core/src/capabilities_stream_monitor.py
└── core/src/agent_shared_flow_orchestrator.py
```

---

## 7.5 Test Strategy (per layer) — issue #328

The suite is organised by AES layer. Each layer has an owner file pattern
and a preferred harness; when adding code, extend the matching pattern.

| Layer | Pattern | Harness | What to add when changing it |
|-------|---------|---------|------------------------------|
| Taxonomy / contracts | `tests/unit_taxonomy_*.py`, `tests/contract_*.py` | pure pytest, no browser | New VO/error/event: constructor + invariant tests; contract changes: method-presence checks (see `TestCancelContract`). |
| Core capabilities | `tests/unit_capability_*.py`, `tests/unit_browser_adapter.py`, `tests/unit_folder_compiler.py` | pytest + `unittest.mock` Playwright fakes (`MagicMock` page/locator, patched DOM helpers and `time`) | New branch/edge: fake the signals (selector visibility, `time` side-effects) — never sleep real seconds. |
| Agent orchestrators | `tests/unit_agent_*.py` | mocked capability protocols; thread-level races via `threading.Event` registries | State transitions (retry/partial/failed/cancelled) as snapshot assertions; cancellation isolation checks. |
| TUI surface | `tests/unit_surface_cli_tui_app.py` | Textual `App.run_test()` async pilot (headless, real widgets) | Drive the app with `asyncio.run(...)`, mutate `_slot_workers`/`_slot_stats` state directly, spy with `patch.object`. No real browser/worker runs. |
| MCP surface | `tests/integration_surface_mcp.py`, `tests/unit_mcp_hardening.py`, `tests/unit_mcp_response_envelope.py` | JSON-RPC envelope + path-boundary assertions over mocked aggregates | New tool/payload field: envelope shape + workspace-path refusal cases. |
| CLI surface | `tests/integration_surface_*.py`, `tests/unit_surface_cli_controller.py` | subprocess argv tests or handler-level mocks | New flag/subcommand: parse-level tests + handler wiring checks. |
| Update Manager | `tests/unit_surface_cli_update_command.py` | patch `_run_subprocess`, `_fetch_json`, `_editable_source_dir` — never spawn real pip/git | New pipeline step: fail-closed refusal case + happy path with mocked transcripts. |
| Swarm | `tests/unit_agent_swarm_orchestrator.py` | fake `IAttachmentPromptAggregate`, real `ThreadPoolExecutor` on tmp dirs | New transition: manifest snapshot after each state change. |
| End-to-end | `tests/contract_qwen_auto.py` (behavior lock), `tests/pipeline_fixtures.py` | fixture HTML replay, headless Chromium fixture server | New UI behavior: extend fixture + lock the behavior map. |

**Rules of thumb**

- Unit tests must not sleep real time, launch real browsers, or touch the
  network; patch `time`, Playwright objects, and subprocess boundaries.
- A fix for a race/cancellation bug ships with a regression test capturing
  the interleaving (see issues #331, #360).
- CI runs `pytest tests/ -v` (see §3); keep the suite under ~2 minutes.
- **Parallel Browser / Swarm Execution Environment** (issue #329): Each concurrent Chromium instance requires ~300–500 MB RAM and adequate `/dev/shm` (minimum 2 GB recommended for a 10-worker Swarm). In containerized CI or Docker, ensure `--shm-size=2gb` or `--ipc=host` is allocated to prevent Chromium renderer crashes.

---

## 7.6 Resilience Drills & Incident Post-Mortem Guidelines (Issue #301)

The system embeds several fault-tolerance primitives (circuit breakers, token-bucket
rate limiters, hard response cutoffs, stream safety breakers, and cancellation isolation).
To validate these primitives against chaotic conditions, engineering teams conduct
the following automated and manual drill scenarios:

1. **Chromium Process Crash / Kill Drill**:
   - **Simulation**: Trigger a long generation or Swarm run, identify the child Chromium PID via `pgrep -f chromium`, and execute `kill -9 <PID>`.
   - **Expected Invariant**: The orchestrator must catch `TargetClosedError` or process loss, record the failure in `JobManager` with status `failed`, trigger retry if attempts remain, and cleanly decrement active worker counters without hanging the caller or crashing the parent process.
2. **Upstream Gateway Rate-Limiting & HTTP 429/503 Drill**:
   - **Simulation**: Mock the Playwright network response router or route `chat.qwen.ai` responses with HTTP status 429/503 or CAPTCHA triggers.
   - **Expected Invariant**: The sliding-window `CircuitBreaker` must record sequential failures; once `threshold` failures occur within `window_sec`, subsequent calls must fail immediately with `CircuitBreakerOpenError` without initiating browser launches.
3. **Stuck / Slow Generation Cutoff Drill**:
   - **Simulation**: Set `timeout_sec=5` on `StreamMonitor` with a prompt that takes >10s.
   - **Expected Invariant**: Exactly upon reaching the 5s cutoff without a terminal DOM event, `ResponseDetectionTimeoutError` is raised, releasing the worker immediately.
4. **Post-Mortem Documentation Process**:
   - In the event of an unhandled browser crash or hung job in production:
     1. Collect per-run forensic logs from `.qwen-web/jobs/<job_id>.json`.
     2. Collect metrics snapshot from `capabilities_observability_setup.py` (`metrics.json`).
     3. Document the sequence of events, root cause (e.g. DOM selector mutation vs network cutoff), and create a reproduction test in `tests/unit_concurrency_guards.py` or `tests/unit_capability_stream_monitor.py`.

---

## 8. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-08-09 | Initial behavior lock: 28 tests, fixture mirror, dead-code removal | dev |
| 2026-08-09 | Restored conftest golden-task fixtures from git HEAD | dev |
| 2026-08-09 | Updated behavior-lock tests & TEST.md to match active P7 QwenClient architecture | dev |
| 2026-08-10 | Updated module inventory to reflect decomposition into focused modules | dev |
| 2026-08-10 | Added validate_response_content to locked behaviors | dev |
