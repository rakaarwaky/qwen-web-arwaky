# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [5.2.2] - 2026-08-20

### Fixed

- Merge pull request #152 from rakaarwaky/fix/mcp-local-json-entrypoint
- fix: align local MCP config with current qwen-web-mcp entrypoint
- fix: align local MCP config with current qwen-web-mcp entrypoint

## [5.2.1] - 2026-08-19

### Fixed

- fix: verify self-update reaches latest release

## [5.2.0] - 2026-08-20

### Added

- test(core): add regression coverage for prompt-file dispatch acknowledgement, slow model-picker hydration, changed-message ACKs, and commit-based navigation

### Fixed

- fix(core): require a real user-turn signal instead of treating composer reset or a disabled send control as dispatch acknowledgement
- fix(core): capture the pre-click message baseline so changed-message ACK detection cannot self-baseline after dispatch
- fix(core): use commit-based chat navigation and readiness-based model-picker selection with retry handling for slow Qwen hydration
- fix(ci): repair the release tag workflow so the release build dispatch command is not duplicated

### Changed

- chore(release): bump version to `5.2.0` across root and module manifests, lock metadata, and embedded skill metadata

---

## [5.1.0] - 2026-08-19

### Added

- feat(core): make response completion event-driven, with `EVENT_OUTPUT_COPIED` as the verified output-success gate
- feat(core): add a 4-hour safety circuit breaker that raises `ResponseDetectionTimeoutError` only when no terminal generation event arrives
- test(core): add regression coverage for delayed responses, transient browser-timeout recovery, output verification, and safety circuit breaking

### Changed

- refactor(core): preserve long-running Qwen generations while using periodic browser reloads for recovery rather than normal response cutoffs
- chore(release): bump version to `5.1.0` across root and module `pyproject.toml` manifests and embedded skill metadata

---

## [5.0.0] - 2026-08-19

### Added

- feat(core): implement **Tier-1 React Fiber Extraction** in `JS_GET_RESPONSE_TEXT` (`taxonomy_core_constant.py`) to bypass Monaco Editor virtual scrolling and extract 100% complete, un-truncated code blocks and Markdown text
- feat(core): enforce default model **`Qwen3.8-Max`** across all chat sessions with automated verification guards
- feat(taxonomy): add dedicated `taxonomy_skill_constant.py` module storing the complete embedded `EMBEDDED_SKILL_MD` template string
- feat(core): update `capabilities_workspace_provisioner.py` to write `EMBEDDED_SKILL_MD` directly into `.agents/skills/qwen-web/SKILL.md` during `qwc init`, removing external file path dependencies
- feat(core): add pre-flight internal extension gatekeeping (`UNSUPPORTED_EXTENSIONS`) to `validate_file()` in `utility_core_validation.py` for 0ms fast-fail rejection of unsupported archive/binary formats (`.zip`, `.tar`, `.gz`, `.exe`)
- feat(cli): add `qwen-web-cli update` self-update and environment synchronization CLI command and service protocol
- feat(installer): add unified cross-platform Python installation script (`install.py`)
- feat(docs): restore demo WebP (`docs/qwen_web_demo.webp`) and GIF (`docs/qwen_web_demo.gif`) animations in README header from git history
- feat(docs): add real sanitized vector SVG screenshot (`design/tui_dashboard.svg`) of `QwenTuiApp` to README
- feat(cli): implement working `--json` output on all prompt subcommands (`prompt-direct`, `prompt-only`, `prompt-with-attachment`, `init`, `update`, `login`) — response envelope to stdout, logs stay on stderr
- feat(cli): map `AuthRequiredError` to **exit code `2`** (previously unreachable — all errors flattened to `1`)
- feat(mcp): add property descriptions, value constraints (100 MB attachment limit, blocked extension list), and examples to all 7 MCP tool schemas for better LLM function-calling accuracy
- feat(tui): add `SESSION: VALID / EXPIRED / N/A` validity badge on mount (checked asynchronously — no UI freeze)
- feat(tui): add **Cancel Run** button, run-in-progress guard, and quit confirmation (Ctrl+Q/Esc warns while a run is active)
- feat(shared): add `detect_processing_failure()` utility (`utility_core_response.py`) unifying `ERROR [...]`/`Failed: N` detection across MCP and TUI surfaces
- feat(shared): extract XDG/OS path resolution into pure constants in `taxonomy_core_constant.py` and move `get_playwright_browsers_path()` to `utility_core_paths.py`
- feat(agent): extract shared prompt-dispatch/response-wait flow into `agent_shared_flow_orchestrator.SharedFlowOrchestrator`, de-duplicating the three prompt orchestrators
- feat(skill): document workspace rule (all files under `.qwen-web/`), orphan-process hazards & safe cleanup, and a hard warning against wrapping runs in external timeouts
- chore(quality): resolve **all 9 `lint-arwaky` AES violations** — `lint-arwaky-cli scan modules/` now reports **0 violations** (2× AES305, 5× AES401, 2× AES203)

### Fixed

- fix(multiplatform): implement OS-native path resolution in `taxonomy_core_constant.py` (`%LOCALAPPDATA%` / `%APPDATA%` on Windows, `~/Library/...` on macOS, XDG on Linux)
- fix(multiplatform): align installer directory name in `scripts/install.py` (`qwen-web` instead of `qwen-web-automation`)
- fix(multiplatform): add cross-platform Playwright browser cache resolution via `get_playwright_browsers_path()` across `surface_cli_doctor_command.py` and `capabilities_update_manager.py`
- fix(multiplatform): add Windows (`chrome.exe`, `msedge.exe`) and macOS (`/Applications/...`) browser binary discovery to `utility_core_browser_binary.py`
- fix(multiplatform): replace Unix-only `Path("/dev/null")` with `Path(os.devnull)` in `root_cli_main_entry.py` and `utility_core_config_factory.py`
- fix(multiplatform): add directory fallback in `capabilities_workspace_provisioner.py` when `os.symlink()` fails on unprivileged Windows environments
- fix(core): upgrade Live DOM Tree Walker fallback with thinking status card pruning (`[class*="thinking"]`, `[class*="status-card"]`) to prevent false-positive skips during response extraction
- fix(cli): resolve `doctor` command unit tests for headless CI environments without active persistent sessions
- fix(security): sanitize `/home/<username>` environment path occurrences in visual SVG documentation to `/home/user`
- fix(ci): enforce strict Ruff and MyPy compliance across shared taxonomy and core modules
- fix(mcp): stop wrapping `ERROR [AUTH_REQUIRED]` result strings in `success: true` envelopes — failures now return `success: false` with a typed error envelope (`AUTH_REQUIRED` / `EXECUTION_ERROR`) and `retryable` hint
- fix(tui): render failed runs as red `FAILED` instead of green `SUCCESS` when the core reports `ERROR [...]` / `Failed: N`
- fix(tui): remove `priority=True` from the Enter binding so pressing Enter inside file-input fields can no longer accidentally launch automation
- fix(cli): remove the misleading `--headless` flag from the `login` parser (login always opens a visible browser)
- fix(tui): run session badge check in a worker thread so `validate_session()` (which opens a browser) no longer freezes the TUI on mount
- fix(core): remove legacy `DEFAULT_TODO` constant and unused imports (`sys` in `utility_core_browser_binary.py`, `SEND_DISABLED_SELECTORS` in `capabilities_stream_monitor.py`)

### Changed

- chore(release): bump version to `5.0.0` across root and module `pyproject.toml` manifests
- refactor(core): `taxonomy_core_constant.py` is now pure constants only (path resolution computed inline, no functions) — fixes AES401 taxonomy-role violations
- refactor(agent): three prompt orchestrators (direct / file / attachment) now share `SharedFlowOrchestrator.dispatch_and_wait_for_response`, removing ~35 duplicated lines per file — fixes AES305
- docs(skill): SKILL.md guidance updated for `.qwen-web/` workspace layout, orphan-process cleanup, and no-external-timeout policy

---

## [4.2.0] - 2026-08-17

### Added

- feat(core): implement proactive **30s Cloud Reload Sync** in `capabilities_stream_monitor.py` to prevent SSE/WAF connection resets during long runs
- feat(core): extend generation timeout ceiling to **900s (15 minutes)** for massive 40KB+ enterprise reports
- feat(core): implement instant **DOM-Stable Exit Condition** (~2s exit detection upon Qwen typing completion)
- feat(core): implement Thread Isolation in `_start_new_chat` (forces `page.goto(CHAT_URL)` when URL contains `/c/*` thread paths)
- feat(core): improve XDG workspace provisioner symlink logic (`~/.local/share/qwen-web/output`, `log`, `qwen_session`)
- feat(cli): add system health diagnostic command `qwen-web-cli doctor [--json]` for self-diagnostics
- feat(cli): add `--json` option to CLI subcommands for machine-readable AI agent output
- feat(tui): add `ConfirmModal` dialog before destructive session deletion
- feat(mcp): add `check_session` and `delete_session` tools to MCP server catalog
- feat(mcp): introduce machine-readable structured JSON response envelopes (`success`, `output_path`, `run_id`, `error`)
- feat(mcp): add pre-flight input validation and path normalization (`~` & relative paths)
- feat(docs): overhaul README.md to sleek minimalist monochrome style and align CLI/MCP FRDs

### Fixed

- fix(tui): remove invalid default attachment paths (`FILE.md`, `DOC.md`) so optional fields do not fail validation
- fix(tui): dynamic package versioning in header title via `importlib.metadata`
- fix(tui): change quit key binding from `q` to `ctrl+q` to prevent accidental exits while typing
- fix(core): auto-generate timestamped output filename (`qwen_output_YYYYMMDD_HHMMSS.md`) when target path is a directory
- fix(mcp): fix `setup_session` contract delegation bug by injecting `ISetupAggregate`
- fix(cli): enhance non-TTY error message with actionable subcommand guidance

---

## [4.1.0] - 2026-08-14

### Added

- feat: update linting rules and ignore specific patterns for browser automation safety
- feat: update README and CLI commands for qwen-web-cli integration
- feat: add test suite initialization for qwen-web-cli
- feat: enhance CI workflow with quality gates and add local gates script
- feat: add atomic JSON file writing utility and update test fixture timestamp
- feat: refactor DOM helper functions and update related capabilities for improved visibility checks
- feat: add utilities for async event-loop isolation and Chrome binary discovery
- feat: add DOM action utilities for Playwright pages
- feat: refine exception handling across multiple modules
- feat: enable AES501 to AES506 rules in lint configuration
- feat: fix AES202/AES203 violations — 0 codacy & aes linter violations
- feat: add IMetricsProtocol import and create QWEN.md file; remove unused Path import
- feat: update protocols to use taxonomy value objects for metrics and status handling
- feat: add Codacy configuration to exclude scripts and tests from analysis
- feat: remove outdated key patterns section from AGENTS.md
- feat: remove unnecessary comment and clean up SKILL.md formatting
- feat: remove obsolete module verification script
- feat: implement atomic file writing with error handling in _write_file_atomic function
- feat: update protocol implementations and enhance class constructors with dependency injection
- feat: enhance class definitions and add __repr__ methods for better debugging

### Fixed

- fix: enforce strict CLI event pipeline gates
- fix(shared): address review feedback for event compatibility
- fix(shared): keep lazy legacy exports analyzer-friendly
- fix(shared): align event value aliases with mypy
- fix(shared): satisfy taxonomy self-lint after refactor
- fix(core): preserve explicit sender timeout
- fix(core): complete capabilities and aggregate test coverage
- Merge pull request #98 from rakaarwaky/fix/mcp-transport-and-spec
- fix(core): refresh circuit breaker state on reconfigure
- fix(mcp): harden stdio proxy validation
- fix: apply CodeRabbit auto-fixes
- fix(core): address PR review pipeline findings
- fix(cli): address review feedback for interactive errors
- fix(core): enforce pipeline routing outcomes and lifecycle gates
- fix(cli): enforce surface precedence and linux lifecycle
- fix(mcp): protect stdio and generate audit log tool
- Merge pull request #47 from rakaarwaky/fix/interactive-missing-appconfig
- fix: pass built config to run command in interactive mode
- Merge pull request #46 from rakaarwaky/arena/019ffc60-qwen-web
- fix: keep manual login browser open and verify session

### Changed

- Merge pull request #107 from rakaarwaky/refactor/shared-taxonomy-event
- refactor(shared): extract event and error taxonomy
- chore(release): v4.1.0
- test(core): honor processing outcome contract
- refactor(core): simplify breaker refresh helper
- style(mcp): organize test imports
- chore(core): keep self-lint compatible
- style(mcp): satisfy lint for generated signatures
- test(mcp): use buffered stdout fixtures
- test(core): avoid private breaker state access
- test(cli): strengthen interactive review coverage
- chore(release): v4.1.0
- Merge pull request #60 from rakaarwaky/arena/019ffcd8-qwen-web
- refactor(core): merge metrics and status into observability (12→10)
- docs(core): split PRD/FRD into 10 capability-aligned FRs
- chore(release): v4.1.0
- Merge pull request #44 from rakaarwaky/worktree/docs-update
- docs: lock scope to Stabilization Mode (PRD, README, FRDs, skill)
- chore(release): v4.1.0
- chore: remove obsolete .last_run_ts fixture file

## [4.1.0] - 2026-08-14

### Added

- Hardened MCP stdio transport with context-aware stdout isolation and audit-log tooling.
- Added aggregate-boundary, CLI LinuxGuard, audit-tail, sender, and DOM-helper regression coverage.
- Added qwen-web-cli integration documentation and quality-gate traceability updates.

### Fixed

- Preserved complete AppConfig values through single, batch, and watcher dispatch.
- Enforced atomic role-relative routing and correct success/failure outcomes.
- Enforced CLI LinuxGuard lock and READY/STOPPING lifecycle notifications while keeping MCP lock-free.
- Refreshed CircuitBreaker state after reconfiguration and expiry.
- Honored SenderConfig fallback and explicit timeout precedence, including SendDispatchError on total dispatch failure.
- Bounded audit JSONL tail reads and handled blank, malformed, truncated, empty, and non-positive-limit cases.
- Preserved manual-login and interactive CLI error propagation.

### Changed

- Consolidated observability metrics and status handling under the current taxonomy and protocol model.
- Strengthened CI, self-lint, Codacy, and release quality gates.

## [4.0.0] - 2026-08-10

### Added

- MCP server mode (`--mcp`) for AI agent integration
- File attachment upload support
- Role-based directory structure for prompt organization
- Watcher mode (`--watch`) for continuous file processing
- Single-instance lock to prevent concurrent runs
- Systemd sd_notify integration for service readiness
- OpenTelemetry distributed tracing
- Sentry error monitoring
- Structured logging with structlog
- Lifecycle event emission system
- XDG-compliant configuration paths
- `init` command for first-time setup
- `login` command for manual authentication
- Regression test suite with behavior locks
- GitHub Actions CI pipeline (lint + test matrix)

### Changed

- Migrated to modular architecture: `prompt_injector`, `sender`, `streamer`, `saver`
- Response extraction now uses JS-based text detection (robust against CSS class changes)
- Default file paths reorganized under `~/.qwen-web/`
- Navigation wait strategy changed to `domcontentloaded`
- Python 3.10+ required

### Fixed

- AuthRequiredError handling in MCP tools and CLI
- Role-based done/failed paths for nested role folders
- Hardcoded user home path replaced with generic `qwc` command
- License metadata string format in pyproject.toml

### Removed

- Legacy role prompts
- Stale task fixtures

## [3.x] - 2026-07-01

### Added

- Initial CLI automation for Qwen AI Web
- Playwright-based browser session management
- Markdown prompt file processing
- Batch and single file modes
- Output file writing with metadata headers
