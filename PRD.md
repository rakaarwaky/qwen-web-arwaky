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

- Goal 1: Achieve 99.9% successful end-to-end pipeline execution for batch
  and watcher workloads on native Linux environments.
- Goal 2: Maintain strict AES 7-layer architectural compliance so AI agents
  can safely modify, refactor, and maintain the codebase without introducing
  regressions.
- Goal 3: Provide seamless 1:1 feature parity between CLI and MCP interfaces
  for local AI agent integration.

## User Personas

- **Indie Developer / Frugal Engineer**: Wants $0 API costs, runs batch markdown prompts locally without burning cash on API tokens, and needs reliable file routing (`input` → `.processing` → `done`/`failed`) and detailed JSONL audit logs.
- **AI Agent (via MCP)**: Interacts with the tool programmatically to send
  prompts, process files, and read audit logs without managing browser
  lifecycles or DOM selectors.
- **System Administrator**: Deploys watcher mode as a background service and
  relies on structured JSON logs for aggregation.

## Scope

- **In scope**: `chat.qwen.ai` web automation, Playwright persistent sessions,
  Batch / Watcher / Single / Interactive / MCP modes, the eight core
  capabilities listed below, structured observability
  (structlog, OpenTelemetry, Sentry), and strict AES 7-layer architecture.
- **Out of scope**: other LLM providers (ChatGPT, Claude, Gemini), official
  REST API integrations, cloud-hosted SaaS deployments, and new product
  features (the project is in **Maintenance & Stabilization Mode**).

Core functional specs live in [`modules/core/FRD.md`](modules/core/FRD.md)
(exactly 8 FRs, one per capability + protocol). CLI and MCP surfaces have
their own FRDs.

## Feature Requirements (Prioritized)

AES rule for Core: **1 FR = 1 capability file + 1 contract protocol**.
Product modes (batch / watcher / single / login / MCP) are how surfaces
compose these FRs, not additional core FRs.

### P0 — Must Have (Core, 10 FRs)

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
- [X]  **FR-005 Send Dispatcher** — Click Send (Enter fallback) only after
  document-parse gate; expose message count / latest text for the stream
  baseline.
  *Accept*: send is blocked while attachment parsing is incomplete.
- [X]  **FR-006 Stream Monitor** — Poll until N identical snapshots and
  generation UI is gone; proactive 30s cloud reload sync for network connection reset recovery;
  900s max-duration ceiling for massive responses (40KB+); immediate exit on DOM completion;
  reject CAPTCHA / error-page content.
  *Accept*: stable response is returned instantly upon generation completion; long 15-minute streaming runs complete without network connection resets; challenge keywords raise `AuthRequiredError` / `OutputValidationError`.
- [X]  **FR-007 Workspace Provisioner** — First-run XDG dirs,
  `.agents/skills/qwen-web/SKILL.md`, `.qwen-web` symlinks (automatically replaces stale local directories with XDG symlinks), `.gitignore`.
  *Accept*: `qwen-web-arwaky init` is idempotent and maintains valid symlinks to XDG targets.
- [X]  **FR-008 Observability Setup** — structlog + optional OTLP traces +
  optional Sentry + process excepthooks; missing telemetry must not block
  start.
  Owns in-process metrics counters and `status.json` writes (merged helpers,
  not extra capabilities).
  *Accept*: process boots with empty `SENTRY_DSN` and no OTLP endpoint.

### P1 — Should Have (Surfaces)

- [X]  **Multi-mode execution**: Batch (folder), Watcher (continuous poll),
  Single (one file), and raw `send_prompt` — all via `ICoreAggregate`.
- [X]  **Persistent session login**: `qwen-web-arwaky login` validates a saved profile
  first; only an invalid session opens a headed browser for CAPTCHA.
- [X]  **Atomic file routing**: `input` → `.processing` → `done` / `failed`
  with circuit breaker and rate limiter in the agent.
- [X]  **MCP server**: 1:1 tools for send / single / batch / watcher /
  session / audit over stdio.

### P2 — Nice to Have

- [X]  **Interactive TUI menu** when the CLI is launched with no args on a TTY.
- [X]  **OpenTelemetry tracing** (optional OTLP HTTP export; part of FR-009).
- [X]  **Sentry error capture** (optional; part of FR-009).

## Non-functional Requirements (High-level)

- **Performance**: Polling overhead must remain <300 ms/cycle. Network
  traffic reduced by 40–60% via aggressive asset blocking (images, fonts,
  media) outside login mode.
- **Security**: Session tokens stored locally in XDG-compliant directories
  with `0o700`. No exfiltration of credentials. Strict prompt-injection
  defense (scraped text is untrusted data, never agent instructions).
- **Reliability**: Atomic file moves and atomic output writes to guarantee
  zero input/output loss. Graceful degradation on DOM changes via multi-tier
  selector fallbacks. Telemetry is best-effort.
- **Maintainability**: Strict AES 7-Layer Pattern (Taxonomy → Utility →
  Contract → Capabilities → Agent → Surface → Root) enforced by custom
  linting. Core stays at **10 FRs**; do not merge capabilities back into
  bundled requirements.

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
  - *Mitigation*: FR-010 single-instance lock on the CLI; MCP skips the lock
    and must not launch a second headed browser against the same profile.
