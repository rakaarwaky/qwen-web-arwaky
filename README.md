# Qwen Web Arwaky

> A Python CLI and MCP server for developers and AI agents that automate `chat.qwen.ai` through a persistent Playwright browser session, without an API key.

## Prerequisites

- Git 2.39 or newer.
- Python 3.10 or newer (CI runs Python 3.12 and 3.13).
- Internet access to download Python packages and Playwright Chromium, and to reach `chat.qwen.ai`.
- A Qwen account for the one-time interactive login.

No Node.js installation or Qwen API key is required.

## Quick Start

The commands below use an isolated virtual environment and work on Linux and macOS:

```bash
git clone https://github.com/rakaarwaky/qwen-web-arwaky.git && cd qwen-web-arwaky
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
qwen-web-arwaky --help
```

Success looks like this:

- `pip` ends with `Successfully installed ... qwen-web-arwaky`.
- Playwright reports that Chromium was downloaded or is already installed.
- The final command prints `Automate chat.qwen.ai without an API key.` and lists actions such as `doctor`, `init`, and `login`.

On Windows PowerShell, create and activate the environment with:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then run the remaining `python ...` and `qwen-web-arwaky --help` commands from the Quick Start.

Provision a working directory and authenticate once before sending prompts:

```bash
qwen-web-arwaky init
qwen-web-arwaky login
```

`init` succeeds when it reports the workspace paths it created. `login` succeeds after the browser opens, authentication completes, and the CLI confirms that the persistent session was saved.

To verify the saved session and local environment:

```bash
qwen-web-arwaky doctor
```

The command prints the diagnostic checks and exits successfully when required components are healthy.

## Project Structure

```text
.
├── modules/
│   ├── cli/                 # CLI commands and Textual terminal UI
│   ├── core/                # Browser automation and orchestration
│   ├── mcp/                 # MCP tool surface
│   ├── shared/              # Contracts, domain types, constants, utilities
│   ├── templates/           # Built-in SDLC role prompt templates
│   ├── root_cli_main_entry.py
│   └── root_mcp_main_entry.py
├── tests/                   # Cross-module and pipeline tests
├── benches/                 # Performance benchmarks
├── scripts/                 # Install, quality-gate, release, and utility scripts
├── deploy/                  # Deployment and alert configuration
├── design/                  # Product design sources and screenshots
├── docs/                    # README media
├── pyproject.toml           # Package metadata, dependencies, and tool settings
├── uv.lock                  # Reproducible dependency lockfile
├── ARCHITECTURE.md          # Layer rules and design decisions
└── TEST.md                  # Test strategy and regression-lock documentation
```

Feature requirements live in `modules/*/FRD.md`; repository-level product requirements live in `PRD.md`. Start in `modules/root_cli_main_entry.py` for CLI composition or `modules/root_mcp_main_entry.py` for MCP composition.

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

## Available Scripts

Run application commands inside the activated virtual environment.

| Command | Purpose | How to confirm success |
| --- | --- | --- |
| `qwen-web-arwaky` | Open the terminal dashboard. | The Textual dashboard renders. |
| `qwen-web-arwaky --help` | List the supported CLI actions. | Help includes `doctor`, `init`, and `login`. |
| `qwen-web-arwaky doctor` | Check browser, session, and environment health. | Diagnostics print and the process exits with status 0. |
| `qwen-web-arwaky init` | Create workspace skills and runtime links. | Created or existing workspace paths are reported. |
| `qwen-web-arwaky login` | Open the interactive one-time Qwen login. | The CLI confirms that the session was saved. |
| `qwen-web-arwaky prompt-direct -t "Explain this repository" -o output.md` | Send an inline prompt and save the response. | `output.md` contains the Qwen response. |
| `qwen-web-arwaky prompt-only -i prompt.md -o output.md` | Send a Markdown prompt file. | `output.md` contains the Qwen response. |
| `qwen-web-arwaky prompt-with-attachment -i prompt.md -a document.pdf -o output.md` | Send a prompt with an attachment. | `output.md` contains the Qwen response. |
| `qwen-web-mcp` | Start the MCP server over standard input/output. | An MCP client can initialize the server; silence while waiting for input is normal. |
| `python -m pytest tests/ modules/shared/tests/ modules/core/tests/ modules/cli/tests/ modules/mcp/tests/ --ignore=tests/test_e2e_pipeline.py -m "not benchmark" -v` | Run the same test selection as CI. | Pytest ends with a passed summary and status 0. |
| `bash scripts/gates.sh` | Run local lint, type, security, architecture, and test gates. | The script ends with `All gates passed`. |
| `python -m build` | Build a source archive and wheel. | Package files appear under `dist/`. |

Use `qwa` as the short alias for `qwen-web-arwaky`. Use `--no-headless` on prompt commands to watch browser automation, and `--json` where supported for machine-readable output.

For MCP client configuration, use the checked-in [`mcp.local.json`](mcp.local.json) as the minimal example.

## Configuration

The application recognizes these environment variable names:

- `QWEN_DEFAULT_MODEL`
- `QWEN_WORKSPACE_ROOT`
- `QWEN_ENABLE_SANDBOX`
- `QWEN_DISABLE_SANDBOX`
- `QWEN_STREAM_SAFETY_TIMEOUT_SEC`
- `QWEN_SWARM_CONCURRENCY`
- `QWEN_WEB_MAX_WORKERS`
- `QWEN_WEB_GITHUB_REPO`
- `QWEN_DOCTOR_DEEP`

MCP client configuration examples are in `mcp.local.json` and `.mcp.json`. Runtime data, state, cache, and configuration follow the platform's XDG directories rather than being committed to the repository. Do not commit session data or credentials.

## Testing

See [`TEST.md`](TEST.md) for test tiers, browser fixtures, regression locks, and the TDD workflow.

A quick smoke test is:

```bash
python -m pytest tests/unit_swarm_to_issues.py -q
```

Success is a progress line ending in `[100%]` and a zero exit status.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).
