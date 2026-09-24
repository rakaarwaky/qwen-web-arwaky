# Contributing

## Development Setup

Follow the root [`README.md`](README.md) Quick Start, then install the development tools used by CI:

```bash
python -m pip install pytest pytest-asyncio pytest-cov pytest-mock ruff mypy bandit build
```

The command succeeds when pip ends with a `Successfully installed` line (or reports that every package is already satisfied).

Read [`AGENTS.md`](AGENTS.md) before changing code. Architecture and naming rules are defined in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Making a Change

1. Add or update a test that demonstrates the intended behavior.
2. Keep feature code in the correct vertical slice under `modules/`.
3. Run the focused test while iterating.
4. Run the local quality gates before opening a pull request.
5. Update user-facing documentation when behavior, commands, or configuration changes.

See [`TEST.md`](TEST.md) for the full test strategy and browser-fixture workflow.

## Quality Gates

```bash
bash scripts/gates.sh
```

Success is the final message `All gates passed`. The script runs formatting and lint checks, type checking, a security scan, architecture checks, template hygiene, and tests.

To mirror the CI test job directly:

```bash
python -m pytest tests/ modules/shared/tests/ modules/core/tests/ modules/cli/tests/ modules/mcp/tests/ --ignore=tests/test_e2e_pipeline.py -m "not benchmark" -v
```

Success is a pytest passed summary and exit status 0. Tests requiring a live authenticated Qwen session are excluded from this command.

## Pull Requests

Keep each pull request focused. In its description, explain the problem, the approach, and the verification commands you ran. Do not include Qwen sessions, secrets, generated browser data, build outputs, or personal configuration.
