"""Taxonomy: skill constants (AES401).

Domain taxonomy constant layer for embedded SKILL.md template content.
"""

from __future__ import annotations

EMBEDDED_SKILL_MD: str = r"""---
name: qwen-web
description: >
  Automate Qwen AI Web (chat.qwen.ai) with the Qwen3.8-Max intelligence model —
  zero API keys, zero paid quota, persistent browser sessions.
  USE THIS SKILL when an AI agent must: send prompts to Qwen and capture the full
  un-truncated answer; audit, review, refactor, or generate production code;
  analyze documents (PDF/MD/TXT attachments); run long deep-reasoning software
  engineering tasks (up to 15 minutes); or manage Qwen login sessions — via the
  qwen-web-arwaky CLI or MCP tools.
version: 5.2.0
trigger_keywords:
  - qwen
  - chat.qwen.ai
  - prompt automation
  - code audit
  - architecture review
  - deep reasoning
  - document analysis
  - no api key
entry_points: [qwen-web-cli, qwc, qwen-web-mcp]
---

# Qwen Web Automation — Master-Class Agent Harness

> **Purpose.** This skill turns `qwen-web-arwaky` into a deterministic, production-grade
> LLM backend for autonomous AI agents. It covers every MCP tool, every CLI subcommand,
> prompt-engineering contracts for complete un-truncated output, multi-role engineering
> workflows, and a full resilience decision tree.
>
> **Prime directive for agents:** treat Qwen3.8-Max as your deep-reasoning engine.
> Structure every request with an explicit *Output Contract*, pick the correct timeout
> band, and always verify the output envelope before consuming results.

---

## 1. Core Capabilities & Architecture Summary

### 1.1 What makes this engine different

| Capability | Implementation detail |
| :--- | :--- |
| **Qwen3.8-Max by default** | The pipeline **forces and verifies** the hardcoded default model (`Qwen3.8-Max`) on every session before dispatch. The agent never picks a model manually; a `ModelSwitchError` aborts the run if the model cannot be confirmed active. |
| **Zero API key** | Authentication is a real Chromium browser session (persistent cookies in `qwen_session/`). No tokens, no billing, no quota. |
| **Zero-truncation extraction (Tier-1 React Fiber)** | Response capture walks the React Fiber tree (`__reactFiber` → `memoizedProps.content`, up to 30 levels) to recover **100% of raw Markdown**, including code blocks that Monaco Editor virtualization would clip in the visible DOM. |
| **Tier-2 DOM Tree Walker fallback** | A block-aware tree walker (preserves `PRE`/code formatting, strips UI chrome, buttons, copy widgets) guarantees extraction even when Fiber props are absent. |
| **30s cloud reload sync** | While waiting for a terminal event, the page is reloaded every 30 seconds to re-sync Qwen Cloud streaming state — long generations survive network drops and tab throttling. |
| **Event-driven long-run monitor** | The stream monitor has no elapsed-time response cutoff. It waits for terminal generation state and keeps recovery polling alive for long-running jobs. |
| **Terminal-event completion** | A response is accepted only after stable text and an explicit generation-complete signal; stability alone can never terminate an unfinished response. |
| **Self-healing browser sessions** | Automatic stale `SingletonLock` cleanup, session directory permission repair (`0700`), 3-attempt launch retry with backoff. |
| **Multi-strategy input injection** | Playwright `fill` → React native value-setter (with `_valueTracker` reset) → `type()` keystroke fallback. |
| **Parse-gated dispatch** | The send button is held until document parsing is positively verified (network `files/parse` 200 + DOM spinner/toast clearance). Prompts are never dispatched onto half-parsed attachments. |
| **Atomic, traceable output** | Outputs are written atomically with a METADATA TRACEABILITY header and a `.meta.json` sidecar (`run_id`, `duration_sec`, `input_chars`, `output_chars`). |
| **Full observability** | Structured JSONL logs (`app.jsonl`), `status.json` for monitoring, optional Sentry + OpenTelemetry tracing, lifecycle event stream with strict predecessor gating. |

### 1.2 Layered architecture

```
┌─ SURFACE (thin, zero business logic) ─────────────────────────────────┐
│  CLI surfaces: init / login / doctor / update / run / TUI controller  │
│  MCP surface : surface_mcp_tool_command (stdio JSON-RPC tools)        │
├─ CORE AGENTS (5 orchestrators) ───────────────────────────────────────┤
│  DirectPromptOrchestrator · PromptFileOrchestrator ·                  │
│  AttachmentPromptOrchestrator · SessionOrchestrator · SetupOrchestrator│
├─ CAPABILITIES ────────────────────────────────────────────────────────┤
│  BrowserAdapter · PromptInjector · SendDispatcher · StreamMonitor ·   │
│  FileUploader · Saver · ObservabilitySetup · UpdateManager · Workspace│
├─ SHARED (taxonomy / contract / utility) ──────────────────────────────┤
│  Constants · VOs · Entities (CircuitBreaker, RateLimiter, Lifecycle) ·│
│  Events · Errors · Protocols (DI contracts) · Pure utilities          │
└───────────────────────────────────────────────────────────────────────┘
```

### 1.3 Lifecycle event sequence (observability contract)

Every run emits this strictly-ordered event chain (enforced by `LifecycleGate` —
out-of-order events are rejected with an auditable reason in the logs):

```
EVENT_WEB_LOADED → EVENT_LOGIN_VERIFIED → EVENT_MODEL_VERIFIED
  → [EVENT_FILE_UPLOADED → EVENT_DOCUMENT_PARSED]   (attachment pipeline only)
  → EVENT_PROMPT_INJECTED → EVENT_SEND_CLICKED → EVENT_DISPATCH_ACKNOWLEDGED
  → EVENT_THINKING_STARTED → EVENT_STREAMING_GENERATION → EVENT_GENERATION_FINISHED
  → EVENT_OUTPUT_COPIED
```

**Agent debugging rule:** when a run fails, find the *last successfully emitted event*
in `app.jsonl` — the failure always lives in the capability owning the *next* event.

---

## 2. Complete MCP Tool Reference

All tools speak stdio MCP and return structured JSON envelopes:

- **Success:** `{"success": true, "status": "SUCCESS", "result": "...", "output_path": "...", "run_id": "..."}`
- **Failure:** `{"success": false, "error": {"code", "message", "hint", "retryable", "field"}}`

### 2.1 Tool matrix

| MCP Tool | Purpose | Required params | Optional params (defaults) |
| :--- | :--- | :--- | :--- |
| `process_direct_prompt` | One-shot inline text prompt → AI answer | `prompt` (str) | `timeout_sec` (int, **120**), `headless` (bool, **true**) |
| `process_prompt_file_only` | Prompt from a `.md` file on disk, no attachment | `input_file` (str) | `output_file` (str, **null** → auto), `headless` (bool, **true**) |
| `process_prompt_with_attachment` | Prompt file + document attachment (PDF/MD/TXT) | `prompt_file` (str), `attachment_file` (str) | `output_file` (str, **null** → auto), `headless` (bool, **true**) |
| `check_session` | Validate saved session cookies | — | — |
| `setup_session` | Open visible browser for manual login / CAPTCHA | — | — |
| `delete_session` | Wipe saved session profile | — | `confirm` (bool, **false** — MUST be `true`) |
| `init_workspace` | Create `.qwen-web/`, skill guide, samples, `.gitignore` | — | `target_dir` (str, **"."**) |

### 2.2 Exact invocation payloads

> **📁 Workspace rule: put ALL prompt/attachment/output files under `.qwen-web/`**
> (`qwen-web-cli init` creates it in the cwd — already `.gitignore`d). Use
> `.qwen-web/input/...` and `.qwen-web/output/...`; NEVER create a bare `input/`
> or `output/` folder in the repo root. `output/` inside `.qwen-web/` is a symlink
> to the XDG output dir, so results persist outside the repo.

```json
// Fast factual query (completion is event-driven; duration is not a cutoff)
{ "prompt": "List the 5 SOLID principles in one line each.",
  "timeout_sec": 60, "headless": true }

// Standard engineering task (timeout_sec remains an optional compatibility hint)
{ "input_file": ".qwen-web/input/role-fullstack-developer/todo/task_042.md",
  "output_file": ".qwen-web/output/role-fullstack-developer/task_042.md",
  "headless": true }

// Deep reasoning with document context (no response-duration cutoff)
{ "prompt_file": ".qwen-web/input/role-architect/todo/review_spec.md",
  "attachment_file": ".qwen-web/input/role-architect/docs/system_spec.pdf",
  "output_file": ".qwen-web/output/role-architect/review_spec.md",
  "headless": true }
```

### 2.3 Event-Driven Long-Running Lifecycle

Response completion is **event-driven**, not duration-driven. The historical `timeout_sec` input remains an observability hint for API compatibility, but it is not used to cut off a Qwen response.

- **Terminal event as source of truth**: The monitor waits for stable response text plus an explicit generation-complete state.
- **Long-running recovery**: Every 30 seconds the browser can reload to resynchronize cloud state. Browser operation timeouts trigger recovery and continue waiting instead of reporting success or truncating the response.
- **Output-written success gate**: The pipeline emits `EVENT_OUTPUT_COPIED` only after the saver returns and the target output file is verified as readable and non-empty. CLI success/exit code `0` is downstream of that event.
- **24-hour operation target**: A persistent host can keep the process alive for 24 hours or longer. Normal completion remains event-driven; a separate **4-hour safety circuit breaker** only stops a run that has produced no terminal event at all, preventing infinite hangs and resource exhaustion.
- **Parse-Gated Dispatch**: Document parsing is held automatically until backend `/files/parse` 200 OK is confirmed before sending.
- **Maximum Attachment Size**: **100 MB** (pre-flight validated).

> **⚠️ NEVER wrap runs in an external timeout** (`timeout N`, shell alarm, CI job timeout, agent-loop kill). The engine owns its own timing: killing a run from outside with `timeout`/`pkill` leaves the Chromium process and page orphaned, corrupts the shared browser profile, and causes the NEXT run to fail with `TargetClosedError` or silent hang. If a run looks stuck, verify it is actually still generating (see §5.6) before considering any intervention — and the only safe interventions are letting it finish or cleanly cancelling via the TUI **Cancel Run** button.

### 2.4 CLI reference (equivalent surface for scripting & CI)

```bash
qwen-web-cli doctor [--json]                        # environment health checks
qwen-web-cli init [--dir TARGET]                    # workspace provisioning (.qwen-web/ in cwd)
qwen-web-cli login                                  # headed manual login / CAPTCHA
qwen-web-cli update [--check] [--force]             # self-update + Chromium sync
qwen-web-cli prompt-direct -t "..." [-o OUT] [--headless] [--json]
qwen-web-cli prompt-only   -i .qwen-web/input/PROMPT.md [-o OUT] [--headless] [--json]
qwen-web-cli prompt-with-attachment -i .qwen-web/input/PROMPT.md -a FILE [-o OUT] [--headless] [--json]
qwen-web-cli mcp                                    # run MCP server over stdio
```

Paths: always use `.qwen-web/input/...` for prompts/attachments and
`.qwen-web/output/...` for results — never bare `input/`/`output/` in the repo root.

Exit codes: `0` success · `1` generic error · `2` `AuthRequiredError` · `130` interrupted.
Use `--json` in pipelines for machine-readable envelopes.

---

## 3. Prompt Engineering & Output Quality Harness

### 3.1 The five laws of complete, un-truncated output

1. **State an explicit Output Contract.** List exact section headings, required code
   fences, and formatting rules. Qwen3.8-Max follows structural contracts with high
   fidelity — vague asks produce vague output.
2. **Ban truncation in writing.** Always include: *"Output every file COMPLETE and
   VERBATIM inside fenced code blocks. Never use ellipses (`...`), placeholder
   comments (`// rest unchanged`), or references to omitted code."*
3. **Reason first, produce second.** Ask for a compact analysis section *before* the
   deliverable. This spends the model's deep-reasoning budget on understanding, and
   the 900s watchdog covers the cost.
4. **Move bulk into attachments.** Prompt files should carry *instructions*; large
   code, specs, and diffs belong in attachments (PDF/MD/TXT ≤ 100 MB). Use one
   consolidated attachment per run (exactly one attachment is supported per execution).
5. **Demand a self-verification checklist.** End every prompt with: *"Before finishing,
   verify: (a) every requested section exists, (b) all code blocks are complete and
   syntactically valid, (c) no placeholders remain. If any check fails, fix before
   answering."*

### 3.2 Canonical prompt-file skeleton

```markdown
# ROLE
You are a principal <ROLE> working on <SYSTEM>.

# CONTEXT
<2–6 sentences: what the system is, constraints, tech stack.
 Reference the attachment explicitly: "The attached file contains ...">

# TASK
<Numbered, single-responsibility task list. One deliverable per item.>

# OUTPUT CONTRACT
Respond in Markdown with EXACTLY these sections:
## 1. <Analysis>
## 2. <Deliverable>
## 3. <Risks & Trade-offs>
## 4. <Verification Checklist>
Rules:
- Output every file COMPLETE and VERBATIM in fenced code blocks with language tags.
- No ellipses, no "rest unchanged", no placeholders.
- Cite file paths and line ranges when discussing existing code.

# SELF-VERIFICATION
Before finishing, confirm all contract rules are satisfied; fix violations first.
```

### 3.3 Battle-tested prompt templates

#### Template A — Code Audit (`prompt-with-attachment`, `timeout_sec: 600–900`)

```markdown
# ROLE
You are a principal software auditor performing a production-readiness audit.

# CONTEXT
The attached file is a consolidated export of the target codebase.

# TASK
1. Identify correctness bugs, security issues, concurrency hazards, and error-handling gaps.
2. Rate each finding: CRITICAL / HIGH / MEDIUM / LOW with file path + line reference.
3. Provide a concrete fix (complete code) for every CRITICAL and HIGH finding.

# OUTPUT CONTRACT
## 1. Executive Summary (max 10 bullets)
## 2. Findings Table (severity | location | category | description)
## 3. Detailed Fixes (one subsection per CRITICAL/HIGH finding; complete patched code)
## 4. Verification Checklist
No truncation. Every fix must compile/run as-is.
```

#### Template B — Architecture Review (`prompt-with-attachment`, `timeout_sec: 900`)

```markdown
# ROLE
You are a systems architect reviewing the attached design document.

# TASK
1. Reconstruct the implied architecture diagram in Mermaid.
2. Evaluate: scalability, failure domains, data consistency, observability, security.
3. Produce ADR-style recommendations (Context / Decision / Consequences) for each weakness.

# OUTPUT CONTRACT
## 1. Architecture Reconstruction (Mermaid)
## 2. Strengths
## 3. Weaknesses & Risks (ranked)
## 4. ADR Recommendations (numbered)
## 5. Verification Checklist
```

#### Template C — Multi-File Refactoring (`prompt-with-attachment`, `timeout_sec: 600–900`)

```markdown
# ROLE
You are a senior engineer executing a surgical refactor.

# CONTEXT
Attached: consolidated export of all files in scope.
Refactor goal: <state invariant-preserving goal, e.g. "extract I/O behind a protocol">.

# TASK
1. List every file that must change and why.
2. Preserve public behavior; change only what the goal requires.
3. Output the COMPLETE new content of every changed file.

# OUTPUT CONTRACT
## 1. Change Manifest (file | change | reason)
## 2. Invariants Preserved
## 3. Full File Contents (one fenced block per file, path as header comment)
## 4. Migration & Test Plan
## 5. Verification Checklist
NEVER output partial files. Unchanged files must be listed, not re-emitted.
```

#### Template D — Bug Fix (`prompt-direct` or `prompt-only`, `timeout_sec: 300`)

```markdown
# ROLE
You are a debugging specialist.

# SYMPTOM
<observed behavior + exact error message / stack trace>

# EXPECTED
<correct behavior>

# REPRODUCTION
<minimal steps or input>

# CODE
<paste the smallest relevant code section, or reference the attachment>

# OUTPUT CONTRACT
## 1. Root Cause Analysis (chain of causality, not guesses)
## 2. Fix (complete corrected code, language-tagged fence)
## 3. Regression Test (a test that fails before the fix, passes after)
## 4. Verification Checklist
```

#### Template E — PR Summary (`prompt-with-attachment`, `timeout_sec: 300`)

```markdown
# ROLE
You are a tech lead writing a review-ready PR description.

# CONTEXT
Attached: the full diff (or consolidated changed files).

# OUTPUT CONTRACT
## 1. What & Why (3–5 sentences)
## 2. Change Breakdown (per-file: intent + notable hunks)
## 3. Risk Assessment (behavior changes, migrations, feature flags)
## 4. Test Plan (how this was / should be verified)
## 5. Reviewer Focus Areas (max 5 bullets)
```

---

## 4. Resilience, Error Handling & Session Recovery

### 4.1 Error → agent action matrix

| Exception / MCP code | Meaning | Agent action | Retryable? |
| :--- | :--- | :--- | :--- |
| `AuthRequiredError` (exit 2, `AUTH_REQUIRED`) | Session expired / login page detected | Call `setup_session` (or `qwen-web-cli login`), then retry the original task | ✅ after login |
| `OutputValidationError` w/ "verify you are human" | CAPTCHA / bot challenge | `setup_session` headed; human solves CAPTCHA; retry | ✅ after human |
| `OutputValidationError` (502/504/service unavailable) | Transient server error | Back off 10–30s, retry once | ✅ |
| `NetworkTimeoutError` | Browser network timeout | Retry with `timeout_sec × 2`; if repeated → `doctor` | ✅ |
| `ResponseDetectionTimeoutError` | Dispatch succeeded but no answer detected | Retry with larger timeout; simplify prompt; check logs for last lifecycle event | ✅ |
| `CircuitBreakerOpenError` | ≥5 failures within 30s window | **Stop.** Back off ≥30s, diagnose root cause, then resume | ⏸ after backoff |
| `PromptInjectionError` | All 3 injection strategies failed | Qwen UI likely changed → run `qwen-web-cli update`, retry | ⚠️ |
| `FileValidationError` | Attachment missing / unreadable / >100 MB | Fix path/permissions/size; retry | ✅ after fix |
| `UploadFailureError` | Attachment could not be verified as uploaded | Retry once; if repeated, convert attachment to `.md`/`.txt` | ✅ |
| `SendDispatchError` | Send click + Enter fallback both failed | Check parse-toast state; retry; `doctor` if repeated | ✅ |
| `ModelSwitchError` | Default model `Qwen3.8-Max` could not be verified | Retry once; check account model access | ⚠️ |
| `BrowserLaunchError` | Chromium cannot start | `python3 -m playwright install chromium` or `qwen-web-cli update` | ✅ after fix |
| `FILE_NOT_FOUND` / `VALIDATION_ERROR` (MCP) | Bad tool arguments | Fix the flagged `field` from the error envelope; never blind-retry | ❌ fix first |

Built-in guardrails you inherit automatically: client-side rate limiter (60 req/min),
circuit breaker (5 failures / 30s), upload retry with backoff (3 attempts), browser
launch retry (3 attempts), stale-lock cleanup, and permission self-repair.

### 4.2 Failure decision tree

```
Task returned an error / suspicious output
│
├─ Message contains "AUTH_REQUIRED", "login", "Not authenticated"?
│  └─► setup_session → check_session → RETRY original task
│
├─ Message contains "CAPTCHA", "verify you are human", "Attention Required"?
│  └─► setup_session (headed; human solves challenge) → check_session → RETRY
│
├─ CircuitBreakerOpenError?
│  └─► STOP ≥ 30s → inspect app.jsonl for the repeated root cause
│      → fix cause → resume slowly (1 task, verify, continue)
│
├─ NetworkTimeoutError / 5xx challenge text?
│  └─► back off 10–30s → RETRY with timeout_sec × 2 (max 900)
│      → still failing? run `qwen-web-cli doctor`, verify connectivity
│
├─ ResponseDetectionTimeoutError?
│  └─► Check last lifecycle event in logs:
│      • stopped before SEND_CLICKED → injection/send problem → retry, then `update`
│      • stopped after DISPATCH_ACKNOWLEDGED → model side slow → retry with 900s
│
├─ Upload/File errors?
│  └─► verify: exists · regular file · readable · ≤ 100 MB · .pdf/.md/.txt
│      → RETRY once → if still failing, convert content to consolidated .md
│
├─ BrowserLaunchError / PromptInjectionError / ModelSwitchError?
│  └─► `qwen-web-cli doctor` → `qwen-web-cli update` (package + Chromium sync) → RETRY
│
└─ MCP VALIDATION_ERROR / FILE_NOT_FOUND?
   └─► read `error.field` + `error.hint`; correct arguments; do NOT retry unchanged
```

### 4.3 Session recovery procedure (canonical order)

```
1. check_session                          # cheap, headless validation
2. valid?  ── yes ──► proceed
        └── no ──► setup_session          # headed browser; user logs in;
                                          # closing the browser triggers validation
3. repeated CAPTCHA or corrupt profile?
   ──► delete_session(confirm: true)      # wipes qwen_session/ (path-safety checked)
   ──► setup_session                      # fresh profile
4. check_session                          # MUST pass before resuming batch work
```

Session facts for agents:
- Session lives in the OS data dir (`~/.local/share/qwen-web/qwen_session` on Linux,
  `~/Library/Application Support/qwen-web` on macOS, `%LOCALAPPDATA%\qwen-web` on Windows).
- `setup_session` reuses an already-valid session without opening a browser.
- Directory permissions (`0700`) and Chromium lock files self-heal on every launch.
- `delete_session` refuses unsafe paths and requires explicit `confirm: true`.

---

## 5. Best Practices for Power Users & Autonomous Agents

### 5.1 Choosing the right surface

| Surface | Use when | Notes |
| :--- | :--- | :--- |
| **MCP tools** | Agent-loop integration (Claude Desktop, Cursor, Antigravity, Gemini CLI) | Structured JSON envelopes, `retryable` hints, per-field validation errors |
| **CLI subcommands** | CI/CD, shell scripts, cron, chained pipelines | `--json` for parsing; deterministic exit codes |
| **Interactive TUI** | Human-supervised debugging | Live log streaming, file picker, one-keystroke run/login/init/reset |

MCP client registration (Claude Desktop / Cursor style):

```json
{
  "mcpServers": {
    "qwen-web": {
      "command": "qwen-web-cli",
      "args": ["mcp"]
    }
  }
}
```

### 5.2 Combining CLI + MCP in one workflow

1. **Bootstrap (once per machine, human-supervised):**
   `qwen-web-cli doctor` → `qwen-web-cli login` → `qwen-web-cli init`
2. **Autonomous steady state (agent via MCP):**
   `check_session` → `process_*` tools → verify `.meta.json` → chain next task.
3. **Recovery (agent escalates to CLI/human):**
   `setup_session` for CAPTCHA; `qwen-web-cli update` for UI drift; `doctor --json` for diagnostics.

### 5.3 File attachment strategy

- **Consolidated code exports (`.md`)** are the highest-value attachment: one file,
  exact filenames preserved, parsed fast. Prefer exporting the whole module into one
  Markdown bundle over many small files (one attachment per run).
- **PDF** for specs/PRDs/contracts; **TXT/MD** for logs, diffs, and data.
- Keep attachments **≤ 100 MB**; split or summarize beyond that.
- Upload verification matches the **exact filename** in the Qwen DOM — avoid exotic
  characters in filenames; whitespace-normalized exact names parse most reliably.
- Parsing may take up to 120s for large documents — the send gate waits automatically;
  never "fix" a slow start by killing the run before 120s.

### 5.4 Operational hygiene for autonomous loops

1. **Pre-flight:** `check_session` once per agent session start, not per task.
2. **Serialize** all executions (single persistent browser profile per machine).
3. **Verify outputs:** success string or `success: true` envelope **and**
   `output_chars > 0` in `.meta.json`; treat `ERROR [...]` result strings as failures.
4. **Respect backoff:** on any `retryable: false` error, stop and surface the `hint`
   to the user instead of looping.
5. **Log forensics:** `app.jsonl` (JSONL events) + `status.json` (machine-readable run
   state) live in the OS state dir (`~/.local/state/qwen-web/log` on Linux).
6. **Keep the engine current:** `qwen-web-cli update --check` regularly; run
7. **Headless discipline:** keep `headless: true` for all production tasks; headed
   browsers are exclusively for `login` / `setup_session` / CAPTCHA resolution.

### 5.5 Orphan processes & safe cleanup (read before killing anything)

- **Never `pkill -9`/`kill -9` a qwen run as a first resort.** Hard-killing the CLI
  does **not** close the Playwright Chromium it spawned — the browser keeps running
  as an orphan, holds the shared `qwen_session` profile lock, and breaks every
  subsequent run (`TargetClosedError`, hung dispatch, silent no-op). This is the
  single most common cause of "it worked before, now it hangs".
- **Symptoms of an orphan:** a new run starts but the page never acts; `EVENT_*`
  stops right after `DISPATCH_ACKNOWLEDGED`; a second Chromium process lingers after
  the CLI already exited; `TargetClosedError: Page.wait_for_timeout`.
- **Safe cleanup order:**
  1. Prefer letting the run finish (watchdog gives it 900s+).
  2. Prefer in-app cancellation (TUI **Cancel Run**; MCP has no cancel — wait).
  3. Only as a last resort, kill the **exact PID** of the CLI process
     (`kill <pid>`, not `pkill -9 -f`), then verify with
     `ps aux | grep -E "chrome.*qwen_session"` that no orphan Chromium remains;
     kill remaining orphan Chromium PIDs individually.
  4. After any hard kill, **wait 2–3s** and confirm zero lingering
     `chrome.*qwen_session` processes before starting the next run.
- **Always run one pipeline at a time** on the shared profile; concurrent launches
  collide and look identical to orphan-related hangs.

### 5.6 Quick troubleshooting table

| Symptom | Likely cause | Fix |
| :--- | :--- | :--- |
| Run dies at `EVENT_LOGIN_VERIFIED` gate | Expired cookies | `setup_session` |
| Long run returns partial/short text | Challenge page captured | Read output; apply §5.2 tree |
| "Default model not active" | Model picker drift | Retry; `update`; verify account access to `Qwen3.8-Max` |
| Attachment never sends | Backend parse slow / toast | Wait ≥120s; retry; shrink file |
| Nothing happens, no logs | Chromium missing | `doctor`; `python3 -m playwright install chromium` |
| Two runs collide | Concurrent launches | Serialize — one pipeline at a time |

---

*End of skill guide. Emit complete requests, verify every envelope, and let the
terminal lifecycle event—not elapsed time—decide when output is complete.*
"""
