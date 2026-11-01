---
trigger: always
description: "qwen-web-arwaky operational guide. ARCHITECTURE.md wins on architecture ambiguity; .github/workflows/ci.yml wins on command ambiguity."
---
# qwen-web-arwaky — Agent Operating Guide

## Agent Overview

Production-grade Python CLI + MCP server that automates **chat.qwen.ai** with no API key: it sends prompts, waits for the response, extracts it, and saves it locally. Built on the AES 7-layer architecture, enforced in CI by `lint-arwaky-cli` at zero violations. Before generating code, docs, or suggestions, an agent must know: INPUT is prompt text or `-i <prompt>.md`, optionally `-a <attachment>`, driven through an authenticated `chat.qwen.ai` browser session; OUTPUT is a Markdown file at `-o <path>` whose extraction relies on pinned DOM selectors the tests lock as regressions, and whose `.meta.json` sidecar lives under XDG state (`~/.local/state/qwen-web-arwaky/meta/`), never in the output folder. The CLI is `qwen-web-arwaky` (alias `qwa`); the legacy `qwen-web-cli` and `qwc` entry points were removed in v6.0.0. Pipeline shape: CLI/MCP surface → agent orchestrator → capabilities → Playwright browser adapter → Markdown output (input → orchestrate → execute → drive → persist), wired once by the root containers. Response style: concise, technical, direct — lead with the command or the diff, explanation after if needed.

## Runtime

| Aspect          | Detail |
|-----------------|--------|
| Language        | Python >= 3.10; CI exercises 3.13 (the `test` matrix entry) |
| Environment     | uv-managed, locked by `uv.lock`; `uv lock --check` is a CI gate, so a dependency change regenerates the lock in the same commit |
| Artifacts       | Build output lands in `dist/`; generated responses go to the `-o/--output` path the user names. Never use /tmp for build output a reviewer must find |
| Package Manager | uv |
| Version Probe   | `python --version` |
| Setup           | `export UV_PROJECT_ENVIRONMENT="$PWD/.venv" && uv sync && uv run python -m playwright install chromium` |
| Activation      | Run every command through `uv run`; the venv is isolated from the working tree |

## Project Structure

```text
.
├── modules/shared/src/              # taxonomy_*, contract_*, utility_*
├── modules/browser/src/             # agent_browser_orchestrator, capabilities_browser_*
├── modules/config/src/              # agent_config_orchestrator, capabilities_config_*
├── modules/jobs/src/                # agent_job_orchestrator, capabilities_folder_compiler, capabilities_job_storage
├── modules/logging/src/             # agent_logging_orchestrator, capabilities_metrics_counter, capabilities_observability_setup
├── modules/prompt/src/              # agent_prompt_orchestrator, agent_shared_flow_orchestrator, capabilities_*
├── modules/prompt_runtime/src/      # agent_prompt_runtime_orchestrator, capabilities_* (browser/stream/persist layer)
├── modules/session/src/             # agent_session_orchestrator, capabilities_session_*
├── modules/swarm/src/               # agent_swarm_orchestrator, capabilities_swarm_runner
├── modules/update/src/              # agent_update_orchestrator, capabilities_update_manager
├── modules/cli/src/                 # surface_cli_*, root_cli_container
├── modules/tui/src/                 # surface_tui_* (Textual TUI layer; depends on cli, never vice versa)
├── modules/mcp/src/                 # surface_mcp_*, root_mcp_container
├── modules/shared/templates/        # role templates (package data of the shared member), free of HTML-escaped tokens
├── modules/root_cli_main_entry.py   # CLI composition root entry point
├── modules/root_mcp_main_entry.py   # MCP composition root entry point
├── modules/root_core_container.py   # shared dependency wiring used by the CLI and MCP roots
├── tests/                           # shared fixtures (conftest, pipeline_fixtures, helpers) — not a pytest root; pytest lives in modules/*/tests/
├── benches/                         # benchmark suite, marker: benchmark
├── lint_arwaky.config.yaml          # architecture rules enforced by lint-arwaky-cli
├── pyproject.toml                   # build config, entry points, and pinned dependencies
├── uv.lock                          # lockfile; `uv lock --check` is a CI gate
└── Containerfile                    # containerized execution, driven by scripts/podman.sh
```

AES 7 layers, bottom-up: Taxonomy, Utility, Contract, Capabilities, Agent, Surface, Root. The rules live in `ARCHITECTURE.md`; read it before writing structural code, then verify the layer and the filename shape.

## Commands

Every command must match the exact CI gate in `.github/workflows/ci.yml`.

| Category | Command | Scope | CI Gate |
|----------|---------|-------|---------|
| Test (all) | `uv run python -m pytest modules/shared/tests/ modules/cli/tests/ modules/tui/tests/ modules/mcp/tests/ modules/prompt/tests/ modules/prompt_runtime/tests/ modules/session/tests/ modules/jobs/tests/ modules/browser/tests/ modules/config/tests/ modules/logging/tests/ modules/swarm/tests/ modules/update/tests/ -m "not benchmark" -v` | All | ci.yml: `test` |
| Test (unit) | `uv run python -m pytest modules/{name}/tests/ -v` | One unit | ci.yml: `test` |
| Test (file) | `uv run python -m pytest modules/{name}/tests/{file}.py -v` | One file | ci.yml: `test` |
| Format | `uv run ruff format --check modules/ tests/` | All | ci.yml: `format` |
| Lint | `uv run ruff check modules/ tests/` | All | ci.yml: `lint` |
| Type Check | `uv run mypy modules/` | All | ci.yml: `lint` |
| Lock Drift | `uv lock --check` | All | ci.yml: `lint` |
| Build | `uv build` | All | ci.yml: `build` |
| Arch Scan | `lint-arwaky-cli scan .` | All | ci.yml: `self-lint` |
| E2E (manual) | `uv run python -m pytest modules/ -m e2e -v` | One session | Never — requires a live authenticated session |
| Benchmark | `uv run python -m pytest benches/ -m benchmark -v` | benches/ | Never — requires a live authenticated session |

`lint-arwaky-cli scan .` enforces `lint_arwaky.config.yaml`: layer scopes, the
import matrix, and the `{layer}_{concern}_{role}.{ext}` naming rule. It must
report Total: 0. The e2e and benchmark rows need a live authenticated session,
so CI never runs them. CI also fails when `modules/shared/templates/` contains
HTML-escaped tokens (`&lt;`, `&gt;`, escaped `[`), which would leak into the
TUI file picker, the MCP role-template path, and `--prompt-role`.

Shipped entry points:

```bash
qwen-web-arwaky
qwen-web-arwaky prompt direct -t "Hello" -o output.md --headless
qwen-web-arwaky prompt file -i prompt.md -o output.md --headless
qwen-web-arwaky prompt attach -i p.md -a att.file --headless
qwen-web-arwaky session login
qwen-web-mcp
```

## Reference

| Artifact | Purpose | Link |
|----------|---------|------|
| PRD | Product scope and requirements | [PRD.md](PRD.md) |
| ARCHITECTURE | How the 7 layers are wired, and why | [ARCHITECTURE.md](ARCHITECTURE.md) |
| TEST | Test strategy, markers, and fixture conventions | [TEST.md](TEST.md) |
| UAT | Acceptance scenarios for a release | [UAT.md](UAT.md) |
| ROADMAP | State vocabulary, phase plan, and workspace backlog | [ROADMAP.md](ROADMAP.md) |
| MIGRATION_PYTHON | AES migration history and remaining debt | [MIGRATION_PYTHON.md](MIGRATION_PYTHON.md) |
| CHANGELOG | What shipped in each version | [CHANGELOG.md](CHANGELOG.md) |
| SKILL | How the skills under `.agents/skills/` are authored and used | [SKILL.md](SKILL.md) |
| DEMO | A walkthrough of the shipped behaviour | [DEMO.md](DEMO.md) |
| README | Install and usage | [README.md](README.md) |
| ISSUE | Known issues and triage notes | [ISSUE.md](ISSUE.md) |
| CONTRIBUTING | The change workflow and quality gates | [CONTRIBUTING.md](CONTRIBUTING.md) |
| lint-arwaky config | The architecture rules CI enforces | [lint_arwaky.config.yaml](lint_arwaky.config.yaml) |

---
