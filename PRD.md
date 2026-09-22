# PRD — qwen-web

## Problem Statement

Power users, system administrators, and local AI agents need to process large
volumes of prompts through `chat.qwen.ai` without relying on official,
rate-limited, or unavailable REST APIs. Manual interaction is slow,
un-auditable, and prone to human error. Existing browser automation scripts
are often brittle, lack observability, and fail to handle edge cases like
CAPTCHAs, network timeouts, or dynamic UI changes gracefully. Furthermore,
maintaining these scripts over time becomes a liability as codebases degrade
into spaghetti code, making AI-assisted maintenance unsafe.

## Goals & Success Metrics

- Goal 1: Achieve 99.9% successful end-to-end pipeline execution for prompt-file
  and inline-text workloads on native Linux environments.
- Goal 2: Maintain strict AES 7-layer architectural compliance so AI agents
  can safely modify, refactor, and maintain the codebase without introducing
  regressions.
- Goal 3: Provide seamless 1:1 feature parity between CLI and MCP interfaces
  for local AI agent integration.

## User Personas

- **Indie Developer / Frugal Engineer**: Wants $0 API costs, runs markdown prompts locally without burning cash on API tokens, and needs detailed JSONL audit logs.
- **AI Agent (via MCP)**: Interacts with the tool programmatically to send
  prompts, process files, and read audit logs without managing browser
  lifecycles or DOM selectors.
- **System Administrator**: Runs prompt automation jobs as scheduled
  background tasks and relies on structured JSON logs for aggregation.

## Scope

- **In scope**: `chat.qwen.ai` web automation, Playwright persistent sessions,
  Single / Inline / Interactive / MCP modes, the 13 core
  capabilities listed below, structured observability
  (structlog, OpenTelemetry, Sentry), and strict AES 7-layer architecture.
- **Out of scope**: other LLM providers (ChatGPT, Claude, Gemini), official
  REST API integrations, and cloud-hosted SaaS deployments. The project is in
  **Stabilization + Targeted Enhancement Mode**; Swarm,
  asynchronous Jobs, and self-update are approved in-scope enhancements under
  change request CR-2026-004.

Core functional specs live in [`modules/core/FRD.md`](modules/core/FRD.md)
(FR-001…FR-013, one per capability + protocol). CLI and MCP surfaces have
their own FRDs.

## Feature Requirements (Prioritized)

AES rule for Core: **1 FR = 1 capability file + 1 contract protocol**.
Product modes (single / inline / login / MCP) are how surfaces
compose these FRs, not additional core FRs.

### P0 — Must Have (Core, 13 capability FRs)

- [X]  **FR-001 Browser Adapter** — Persistent Chromium/Playwright context,
  stale-lock cleanup, `0o700` session dir, asset blocking, auth
  triple-check (URL + login form + chat textarea), and guaranteed thread isolation
  (`_start_new_chat` auto-navigates away from `/c/*` thread URLs).
  *Accept*: headless run reuses a `login` profile; login page raises
  `AuthRequiredError`; existing thread URLs auto-reset to a clean chat.
- [X]  **FR-002 File Uploader** — Local-file pre-flight (exists, readable,
  ≤100 MB) and Qwen UI attach with retry/backoff; degrade to text-only on
  failure.
  *Accept*: oversized file never opens the chooser; successful attach shows
  a file card.
- [X]  **FR-003 Output Saver** — Atomic UTF-8 write of the AI response plus
  metadata header and `.meta.json` sidecar.
  *Accept*: crash mid-write does not leave a truncated destination file.
- [X]  **FR-004 Prompt Injector** — Prepare and inject prompt text via
  four-tier DOM strategy (React setter + synthetic `keyup` sync → ContentEditable → `fill` → `type`).
  *Accept*: empty text is rejected; React controlled state updates reliably without input text reset.

### Reliability measurement

One pipeline execution is one prompt file dispatched to a terminal success or
explicit error envelope. The success rate is `successful_executions /
total_executions` over a rolling 24-hour window. Persistent counters are stored
in `metrics.json` under the application state directory. Emit WARNING below
99.5% and CRITICAL below 99.0%.
- [X]  **FR-005 Send Dispatcher** — Click Send (Enter fallback) only after
  document-parse gate; expose message count / latest text for the stream
  baseline.
  *Accept*: send is blocked while attachment parsing is incomplete.
- [X]  **FR-006 Stream Monitor** — Poll until N identical snapshots and
  generation UI is gone; proactive 30s cloud reload sync for network connection reset recovery;
  `timeout_sec` hard cutoff per call (default surfaces: 120s; set higher for
  massive responses), event-driven stall detection; immediate exit on DOM completion;
  reject CAPTCHA / error-page content. The absolute safety breaker defaults
  to 4h and is tunable via `QWEN_STREAM_SAFETY_TIMEOUT_SEC`.
  *Accept*: stable response is returned instantly upon generation completion; long streaming runs complete without network connection resets when their `timeout_sec` budget allows; challenge keywords raise `AuthRequiredError` / `OutputValidationError`.
- [X]  **FR-007 Workspace Provisioner** — First-run XDG dirs,
  `.agents/skills/qwen-web/SKILL.md`, `.qwen-web` symlinks (automatically replaces stale local directories with XDG symlinks), `.gitignore`.
  *Accept*: `qwen-web-arwaky init` is idempotent and maintains valid symlinks to XDG targets.
- [X]  **FR-008 Observability Setup** — structlog + optional OTLP traces +
  optional Sentry + process excepthooks; missing telemetry must not block
  start.
  Owns in-process metrics counters and `status.json` writes (merged helpers,
  not extra capabilities).
  *Accept*: process boots with empty `SENTRY_DSN` and no OTLP endpoint.
- [X] **FR-009 Folder Compiler** — Import-aware folder and Markdown compilation.
- [X] **FR-010 Folder-to-Attachment Adapter** — Convert compiled folders into uploadable attachments.
- [X] **FR-011 Job Manager** — Persist and poll asynchronous MCP jobs with bounded worker execution.
- [X] **FR-012 TUI Slot Configuration** — Resolve validated per-slot prompt, attachment, and output plans.
- [X] **FR-013 Update Manager** — Check package releases, synchronize Chromium, and report health.

### P1 — Should Have (Surfaces)

- [X]  **Multi-mode execution**: Single (one file), prompt-with-attachment,
  inline direct, and raw prompt dispatch — all via the aggregate contracts
  (`IPromptFileAggregate`, `IAttachmentPromptAggregate`,
  `IDirectPromptAggregate`).
- [X]  **Persistent session login**: `qwen-web-arwaky login` validates a saved profile
  first; only an invalid session opens a headed browser for CAPTCHA.
- [X]  **Timestamped input processing**: input files are uniquely named by the
  producer; success/failure status is recorded in JSONL logs and job metrics,
  and input files remain in place.
- [X]  **MCP server**: live tools for direct prompts, prompt files, attachments,
  session management, workspace initialization, and asynchronous job status.
- [X]  **Session-expiry containment (business rule)**: a session that expires
  mid-run during long-running Swarm or multi-slot TUI operations fails only
  the affected agent/slot with a per-run `AUTH_REQUIRED` isolation — sibling
  runs keep their in-flight browsers and complete; the surface reports an
  overall partial/failed status with a re-login hint, never a global abort
  of healthy sibling work. Recovery path: re-login, then retry the failed
  slots/agents.

### P2 — Nice to Have

- [X]  **Interactive TUI menu** when the CLI is launched with no args on a TTY.
- [X]  **OpenTelemetry tracing** (optional OTLP HTTP export; part of FR-008).
- [X]  **Sentry error capture** (optional; part of FR-008).

## Non-functional Requirements (High-level)

- **Performance**: Polling overhead must remain <300 ms/cycle. Network
  traffic reduced by 40–60% via aggressive asset blocking (images, fonts,
  media) outside login mode.
- **Security**: Session tokens stored locally in XDG-compliant directories
  with `0o700`. Output files written with `0o600` owner confidentiality.
  No exfiltration of credentials. Strict prompt-injection defense (scraped
  text is untrusted data, never agent instructions). Supply chain integrity:
  self-update pins release commit SHAs. SAST & dependency compliance scanning
  supported via Bandit and pip-audit (Issue #350).
- **Reliability**: Atomic file moves and atomic output writes to guarantee
  zero input/output loss. Graceful degradation on DOM changes via multi-tier
  selector fallbacks. Telemetry is best-effort.
- **Maintainability**: Strict AES 7-Layer Pattern (Taxonomy → Utility →
  Contract → Capabilities → Agent → Surface → Root) enforced by custom
  linting. Core inventory is **13 capability FRs**; keep one FR per capability and do not
  merge independently testable capabilities back into bundled requirements.

## Open Questions / Risks

- **Risk**: `chat.qwen.ai` UI DOM changes frequently, breaking Playwright
  selectors.
  - *Mitigation*: Multi-tier fallback selectors and JS extraction that
    relies on structural heuristics. Behavior locked by
    `tests/fixtures/qwen_fixture.html`.
- **Risk**: Cloudflare/CAPTCHA challenges in headless mode.
  - *Mitigation*: Manual `--login` solves CAPTCHA in a headed browser and
    saves persistent session state for subsequent headless runs.
- **Risk**: Two processes sharing one Chromium profile corrupt the session.
  - *Mitigation*: single-instance lock on the CLI (see CLI FRD); MCP skips
    the lock and must not launch a second headed browser against the same
    profile.
- **Risk**: Unbounded concurrent browser execution exhausting system memory (Issue #365).
  - *Mitigation*: Global concurrency bounds (`DEFAULT_MAX_WORKERS=10`, `QWEN_WEB_MAX_WORKERS`,
    `QWEN_SWARM_CONCURRENCY=10`). Ephemeral session cloning uses copy-on-write
    storage to minimize disk footprint across workers.

