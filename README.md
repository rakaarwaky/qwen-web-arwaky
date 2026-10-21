# Qwen Web Arwaky

> A Python CLI and MCP server for developers and AI agents that automate `chat.qwen.ai` through a persistent Playwright browser session, without an API key.

## Prerequisites

- Git 2.39 or newer.
- Python 3.10 or newer (CI runs Python 3.12 and 3.13).
- Internet access to download Python packages and Playwright Chromium, and to reach `chat.qwen.ai`.
- A Qwen account for the one-time interactive login.

No Node.js installation or Qwen API key is required.

## Quick Start

### Recommended: Production XDG Installation

Install immutably to user XDG directories (`~/.local/share/qwen-web-arwaky/venv/` and `~/.local/bin/`):

```bash
git clone https://github.com/rakaarwaky/qwen-web-arwaky.git && cd qwen-web-arwaky
./scripts/install.sh
qwa --help
```

### Standalone Virtual Environment Installation

For an isolated virtual environment (Linux and macOS):

```bash
git clone https://github.com/rakaarwaky/qwen-web-arwaky.git && cd qwen-web-arwaky
python3 -m venv .venv && source .venv/bin/activate
python -m pip install .
python -m playwright install chromium
qwen-web-arwaky --help
```

> **Installation Policy**: Editable installation (`pip install -e .`) is strictly forbidden. The application runtime must never execute directly from the repository source tree (`modules/`). All installations must copy the package code immutably into the destination environment.

Success looks like this:

- `pip` ends with `Successfully installed ... qwen-web-arwaky`.
- Playwright reports that Chromium was downloaded or is already installed.
- The final command prints `Automate chat.qwen.ai without an API key.` and lists
actions such as `doctor`, `init`, and `session login`.

On Windows PowerShell, create and activate the environment with:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then run the remaining `python ...` and `qwen-web-arwaky --help` commands from the Quick Start.

Provision a working directory and authenticate once before sending prompts:

```bash
qwen-web-arwaky init
qwen-web-arwaky session login --name personal
```

`init` succeeds when it reports the workspace paths it created. `session login`
succeeds after the browser opens, authentication completes, and the CLI confirms
that the persistent session was saved.

To verify the saved session and local environment:

```bash
qwen-web-arwaky doctor
```

The command prints the diagnostic checks and exits successfully when required components are healthy.

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md).

At a high level, both the CLI and MCP surfaces call agent orchestrators. Agents coordinate capability implementations through shared contracts; capabilities adapt Playwright, filesystem, and observability I/O. Shared taxonomy and utility modules contain stable types and reusable pure logic. Root entry points compose these layers.

```text
CLI / MCP surfaces
        |
        v
Agent orchestrators
        |
        v
Capabilities -----> Playwright / filesystem / telemetry
        |
        v
Shared contracts, taxonomy, and utilities
```

The workspace layout and module map live in [AGENTS.md](AGENTS.md) Project Structure; feature requirements live in `modules/*/FRD.md`; repository-level product requirements live in `PRD.md`. Start in `modules/root_cli_main_entry.py` for CLI composition or `modules/root_mcp_main_entry.py` for MCP composition.

## Available Scripts/Commands

Run application commands inside the activated virtual environment.

| Command | Purpose | How to confirm success |
| --- | --- | --- |
| `qwen-web-arwaky` | Open the terminal dashboard. | The Textual dashboard renders. |
| `qwen-web-arwaky --help` | List the supported CLI actions. | Help includes `doctor`, `init`, and `session login`. |
| `qwen-web-arwaky doctor` | Check browser, session, and environment health. | Diagnostics print and the process exits with status 0. |
| `qwen-web-arwaky init` | Create workspace skills and runtime links. | Created or existing workspace paths are reported. |
| `qwen-web-arwaky session login --name personal` | Open the interactive one-time Qwen login. | The CLI confirms that the session was saved. |
| `qwen-web-arwaky session list` | List registered sessions with health state. | The session pool table prints. |
| `qwen-web-arwaky session health` | Ping every session with a live headless probe. | Each session reports healthy or limited. |
| `qwen-web-arwaky session remove <id-or-name>` | Drop a session entry and its Chromium profile. | The pool entry and profile are removed. |
| `qwen-web-arwaky prompt direct -t "Explain this repository" -o output.md` | Send an inline prompt and save the response. | `output.md` contains the Qwen response. |
| `qwen-web-arwaky prompt file -i prompt.md -o output.md` | Send a Markdown prompt file. | `output.md` contains the Qwen response. |
| `qwen-web-arwaky prompt attach -i prompt.md -a document.pdf -o output.md` | Send a prompt with an attachment. | `output.md` contains the Qwen response. |
| `qwen-web-arwaky job submit -i prompt.md` | Queue a background prompt job. | The job ID prints with a poll hint. |
| `qwen-web-arwaky job status <job-id>` | Query one background job. | The job record prints. |
| `qwen-web-arwaky job list` | List recent background jobs. | The recent-jobs table prints. |
| `qwen-web-arwaky swarm start <path>` | Fan a file or folder out across role templates. | The Swarm snapshot prints with a poll hint. |
| `qwen-web-arwaky observability status` | Show the status file and metrics snapshot. | The status table prints. |
| `qwen-web-arwaky observability report` | Write the quality report for the last run. | The report path prints. |
| `qwen-web-arwaky update --check` | Compare current and latest versions without installing. | The version verdict prints. |
| `qwen-web-mcp` | Start the MCP server over standard input/output. | An MCP client can initialize the server; silence while waiting for input is normal. |
| `python -m pytest modules/shared/tests/ modules/cli/tests/ modules/mcp/tests/ modules/prompt/tests/ modules/session/tests/ modules/jobs/tests/ modules/browser/tests/ modules/config/tests/ modules/logging/tests/ modules/swarm/tests/ modules/update/tests/ -m "not benchmark" -v` | Run the same test selection as CI. | Pytest ends with a passed summary and status 0. |
| `bash scripts/ci.sh` | Run local lint, type, security, architecture, and test gates. | The script ends with `All 7 gates passed`. |
| `python -m build` | Build a source archive and wheel. | Package files appear under `dist/`. |

Use `qwa` as the short alias for `qwen-web-arwaky`. Use `--no-headless` on prompt commands to watch browser automation, and `--json` where supported for machine-readable output.

## Configuration

[`.env.example`](.env.example) is the committed environment variable contract: every
recognized variable with its purpose, default, and sensitivity. Copy it to `.env` and
review each value. `qwen-web-arwaky doctor --json` echoes the effective configuration with
secret values masked, and reports any `QWEN_*` / `QWA_*` variable set but not in the
registry — a typo otherwise changes runtime behaviour silently.

Zero configuration is the supported default: with no `.env`, no exports, and no
settings file, every value below falls back to the registry default. The TUI
Settings screen's **Runtime Overrides** tab is the place to change one — it
lists the same registry `doctor` prints, shows the value actually in force, and
writes the change to `~/.config/qwen-web-arwaky/settings.env`. That file is
loaded before the container is built, so an override survives a restart. A
shell export still outranks it, and clearing a field returns the value to its
default rather than blanking it.

Behaviour switches worth knowing:

- `QWEN_MODEL` / `QWEN_DEFAULT_MODEL` — target model (default `Qwen3.8-Max`); the `--model`
  flag overrides both. A name the picker does not offer degrades to the first available
  model with a WARNING instead of failing the run.
- `QWEN_ENABLE_SANDBOX` / `QWEN_DISABLE_SANDBOX` — Chromium runs with its OS sandbox by
  default; `QWEN_DISABLE_SANDBOX` is the explicit opt-out for hosts that cannot provide
  seccomp or user namespaces.
- `QWEN_WEB_MAX_WORKERS` / `QWEN_SWARM_CONCURRENCY` — browser fan-out. Unset derives the
  worker count from available host memory (~700 MiB per Chromium); set explicitly to
  override, clamped to the derived capacity.
- `QWEN_REQUEST_TIMEOUT_SEC` — ceiling on how long a single response may take (default
  `600`). A non-numeric value is refused by the registry and never stored.
- `SENTRY_DSN` / `OTEL_EXPORTER_OTLP_ENDPOINT` — error tracking and tracing. With
  `ENVIRONMENT=production` and neither set, `doctor` reports a warning.
- `QWEN_WORKSPACE_ROOT` — override the workspace root directory.
- `QWEN_STREAM_SAFETY_TIMEOUT_SEC` — global ceiling for the response-detection loop.
- `QWEN_WEB_GITHUB_REPO` — GitHub repo the self-update checks against.
- `QWEN_DOCTOR_DEEP` — enable the slow Playwright cold-start probe in `doctor`.

Operator runbooks for each `ErrorCategory` live in [`docs/`](docs/);
`doctor` failure messages link to them.

A reference systemd unit with `MemoryMax`, `TasksMax`, and a bounded worker count is in
[`deploy/qwen-web-arwaky.service`](deploy/qwen-web-arwaky.service).

Runtime data, state, cache, and configuration follow the platform's XDG directories rather than being committed to the repository. Do not commit session data or credentials.

Generated responses land in `~/.local/share/qwen-web-arwaky/output/`; the `.meta.json` run-traceability sidecar for each response lives separately, under `~/.local/state/qwen-web-arwaky/meta/`, mirroring the artifact's relative path.

## Testing

See [`TEST.md`](TEST.md) for test tiers, browser fixtures, regression locks, and the TDD workflow.

A quick smoke test is:

```bash
python -m pytest modules/swarm/tests/unit_swarm_to_issues.py -q
```

Success is a progress line ending in `[100%]` and a zero exit status.

Real-session pipeline checks (need a logged-in `chat.qwen.ai` session) run
outside pytest:

```bash
python3 scripts/real_tests.py            # direct + file + attach, headful by default
python3 scripts/real_tests.py --headless -2   # prompt-file pipeline only, headless
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).
