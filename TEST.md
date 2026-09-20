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
| `prompt_injector.py` | `find_input` | Matches `textarea.message-input-textarea` | Live probe 2026-08-09 |
| `prompt_injector.py` | `inject_text` | Tier 1: React `HTMLTextAreaElement.prototype` setter; Tier 2: clipboard paste; Tier 3: `fill()`/`type()` | Live probe 2026-08-09 |
| `prompt_injector.py` | `type_slowly` | Character-by-character typing with error escalation | Live probe 2026-08-09 |
| `file_uploader.py` | `upload_file_attachment` | `.mode-select-open` → `Upload attachment` → file chooser → `.message-input-column-file` card | Live probe 2026-08-09 |
| `sender.py` | `click_send` | Clicks `button[aria-label*='Send']`; Enter fallback | Live probe 2026-08-09 |
| `sender.py` | `count_messages` | Counts `.markdown-body` nodes under `#chatLog` | Live probe 2026-08-09 |
| `sender.py` | `latest_message_text` | Returns `.markdown-body` text of last assistant node | Live probe 2026-08-09 |
| `streamer.py` | `validate_response_content` | Detects CAPTCHA challenges, server error pages, empty responses | Live probe 2026-08-09 |
| `streamer.py` | `wait_for_response` | Stability loop with output validation | Live probe 2026-08-09 |
| `browser.py` | `SessionCheck.is_alive` | Verifies page readiness and textarea presence | Live probe 2026-08-09 |
| `browser.py` | `SessionCheck.check_auth` | Detects login redirects and missing textarea | Live probe 2026-08-09 |
| `qwen_client.py` | `send_file` | Full pipeline: new chat → attach → inject → parse wait → send → response | Live probe 2026-08-09 |
| `qwen_client.py` | `send_prompt` | Same pipeline without attachment | Live probe 2026-08-09 |

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

| Module | Target | Typical | Notes |
|--------|--------|---------|-------|
| `modules/shared/src/taxonomy_core_constant.py` | 100% | 100% | Selectors & constants — fully locked |
| `modules/core/src/capabilities_prompt_injector.py` | 100% UI-behavior | ~72% | Uncovered: error branches, clipboard fallback edge cases |
| `modules/core/src/capabilities_send_dispatcher.py` | 100% | ~90% | Uncovered: PlaywrightError fallback branches |
| `modules/core/src/capabilities_stream_monitor.py` | 100% | ~85% | Uncovered: network timeout branches |
| `modules/core/src/agent_shared_flow_orchestrator.py` | — | ~19% | Locked via `test_pipeline_fixtures.py` state management |

The **72-85% coverage** is the expected steady state: the uncovered percentages
are `except PlaywrightError`, `start_new_chat` network redirects,
`_wait_for_auth` login detection, and other error-handling branches that
require live network/auth and are tested separately via `test_e2e_pipeline.py`.

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
├── test_qwen_client_behavior.py         # Behavior-lock tests (TDD safety net)
├── test_pipeline_fixtures.py            # Fixture state management tests
├── test_e2e_pipeline.py                 # Live E2E pipeline tests
└── manual_probe.py                      # Ad-hoc headed probe for live UI debugging
modules/
├── shared/src/taxonomy_core_constant.py  # Selectors & constants
├── core/src/capabilities_prompt_injector.py
├── core/src/capabilities_send_dispatcher.py
├── core/src/capabilities_stream_monitor.py
└── core/src/agent_shared_flow_orchestrator.py
```

---

## 8. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-08-09 | Initial behavior lock: 28 tests, fixture mirror, dead-code removal | dev |
| 2026-08-09 | Restored conftest golden-task fixtures from git HEAD | dev |
| 2026-08-09 | Updated behavior-lock tests & TEST.md to match active P7 QwenClient architecture | dev |
| 2026-08-10 | Updated module inventory to reflect decomposition into focused modules | dev |
| 2026-08-10 | Added validate_response_content to locked behaviors | dev |
