---
trigger: always
description: "qwen-web-arwaky operational guide. ARCHITECTURE.md wins on architecture ambiguity; .github/workflows/ci.yml wins on command ambiguity."
---
# qwen-web-arwaky — Agent Operating Guide

Production-grade Python CLI + MCP server that automates **chat.qwen.ai** with no
API key: it sends prompts, waits for the response, extracts it, and saves it
locally. Built on the AES 7-layer architecture, enforced in CI by
`lint-arwaky-cli` at zero violations.

## Runtime

- Language: Python >= 3.10; CI exercises the 3.12 and 3.13 matrix entries.
- Environment: uv-managed, locked by `uv.lock`; `uv lock --check` is a CI gate,
  so a dependency change regenerates the lock in the same commit.
- Artifacts: build output lands in `dist/`; generated responses go to the
  `-o/--output` path the user names. Never use /tmp for build output a
  reviewer must find.
- Package manager: uv.

```bash
python --version
export UV_PROJECT_ENVIRONMENT="$HOME/.local/share/qwen-web-arwaky/venv" && uv sync
uv run python -m playwright install chromium
```

## Project Quick Facts

INPUT  = prompt text or `-i <prompt>.md`, optionally `-a <attachment>`,
driven through an authenticated `chat.qwen.ai` browser session.
OUTPUT = a Markdown file at `-o <path>`; extraction relies on pinned DOM
selectors that the tests lock as regressions.

Current release: **v6.4.0**. The legacy `qwen-web-cli` and `qwc` entry points
were removed in v6.0.0, so the CLI is `qwen-web-arwaky` (alias `qwa`).

Concise, technical, direct response style. Lead with the command or the diff;
explanation after, if needed.

## Pipeline

CLI/MCP surface → agent orchestrator → capabilities → Playwright browser
adapter → Markdown output
input → orchestrate → execute → drive → persist
orchestrated by the root containers, which wire every dependency once.

## Project Structure

```text
modules/shared/src/   taxonomy_*, contract_*, utility_*
modules/browser/src/  agent_browser_orchestrator, capabilities_browser_adapter
modules/config/src/   agent_config_orchestrator, capabilities_config_*
modules/jobs/src/     agent_job_orchestrator, capabilities_folder_compiler, capabilities_job_storage
modules/logging/src/  agent_logging_orchestrator, capabilities_metrics_counter
modules/prompt/src/   agent_prompt_orchestrator, agent_shared_flow_orchestrator, capabilities_*
modules/session/src/  agent_session_orchestrator, capabilities_session_*
modules/swarm/src/    agent_swarm_orchestrator, capabilities_swarm_runner
modules/update/src/   agent_update_orchestrator, capabilities_update_manager
modules/cli/src/      surface_cli_*, root_cli_container
modules/mcp/src/      surface_mcp_*, root_mcp_container
modules/templates/    role templates, free of HTML-escaped tokens
root_cli_main_entry.py, root_mcp_main_entry.py
tests/                unit, integration, e2e, fixtures/, conftest.py
benches/              benchmark suite, marker: benchmark
lint_arwaky.config.yaml, pyproject.toml, uv.lock
Containerfile         containerized execution, driven by scripts/podman.sh
```

AES 7 layers, bottom-up: Taxonomy, Utility, Contract, Capabilities, Agent,
Surface, Root. The rules live in `ARCHITECTURE.md`; read it before writing
structural code, then verify the layer and the filename shape.

## Commands

Every command must match the exact CI gate.

```bash
# Tests
uv run python -m pytest tests/ modules/shared/tests/ modules/cli/tests/ \
  modules/mcp/tests/ modules/prompt/tests/ modules/session/tests/ \
  modules/jobs/tests/ modules/browser/tests/ modules/config/tests/ \
  modules/logging/tests/ modules/swarm/tests/ modules/update/tests/ \
  --ignore=tests/test_e2e_pipeline.py -m "not benchmark" -v   # what it covers
uv run python -m pytest modules/{name}/tests/ -v              # one unit
uv run python -m pytest tests/test_{name}.py -v               # one file
# Lint / types / architecture
uv run ruff format --check modules/ tests/                    # matches ci.yml {job name}
uv run ruff check modules/ tests/                              # matches ci.yml {job name}
uv run mypy modules/                                           # exact config-file flags
uv lock --check                                                # matches ci.yml {job name}
lint-arwaky-cli scan .                                         # architecture scanner
uv build
```

`lint-arwaky-cli scan .` enforces `lint_arwaky.config.yaml`: layer scopes, the
import matrix, and the `{layer}_{concern}_{role}.{ext}` naming rule. It must
report Total: 0. The e2e and benchmark selections need a live authenticated
session, so CI never runs them:

```bash
uv run python -m pytest tests/ -m e2e -v
uv run python -m pytest benches/ -m benchmark -v
```

CI also fails when `modules/templates/` contains HTML-escaped tokens
(`&lt;`, `&gt;`, escaped `[`), which would leak into the TUI file picker, the
MCP role-template path, and `--prompt-role`.

Shipped entry points:

```bash
qwen-web-arwaky
qwen-web-arwaky prompt-direct -t "Hello" -o output.md --headless
qwen-web-arwaky prompt-only -i prompt.md -o output.md --headless
qwen-web-arwaky prompt-with-attachment -i p.md -a att.file --headless
qwen-web-arwaky login
qwen-web-mcp
```

## Related Documents

- [PRD.md](PRD.md): product scope and requirements.
- [ARCHITECTURE.md](ARCHITECTURE.md): how the 7 layers are wired, and why.
- [TEST.md](TEST.md): test strategy, markers, and fixture conventions.
- [UAT.md](UAT.md): acceptance scenarios for a release.
- [ROADMAP.md](ROADMAP.md): state vocabulary, phase plan, and workspace backlog.
- [MIGRATION_PYTHON.md](MIGRATION_PYTHON.md): AES migration history and remaining debt.
- [CHANGELOG.md](CHANGELOG.md): what shipped in each version.
- [SKILL.md](SKILL.md): how the skills under `.agents/skills/` are authored and used.
- [DEMO.md](DEMO.md): a walkthrough of the shipped behaviour.
- [README.md](README.md): install and usage.
- [ISSUE.md](ISSUE.md): known issues and triage notes.
- [CONTRIBUTING.md](CONTRIBUTING.md): the change workflow and quality gates.
- [lint_arwaky.config.yaml](lint_arwaky.config.yaml): the architecture rules CI enforces.

---
