# Contributing

## Principles

- Read [`AGENTS.md`](AGENTS.md) before changing code. Architecture and naming rules are defined in [`ARCHITECTURE.md`](ARCHITECTURE.md).
- Keep each change focused: one problem, one pull request.
- A change is not done until the gates in [Quality Verification & PR Process](#quality-verification--pr-process) pass locally.

## Development Setup

Follow the root [`README.md`](README.md) Quick Start, then install the development tools used by CI:

```bash
python -m pip install pytest pytest-asyncio pytest-cov pytest-mock ruff mypy bandit build
```

The command succeeds when pip ends with a `Successfully installed` line (or reports that every package is already satisfied).

## Feature Change

1. Add or update a test that demonstrates the intended behavior.
2. Keep feature code in the correct vertical slice under `modules/`.
3. Run the focused test while iterating.
4. Run the local quality gates before opening a pull request.
5. Update user-facing documentation when behavior, commands, or configuration changes.

See [`TEST.md`](TEST.md) for the full test strategy and browser-fixture workflow.

## Documentation Change

1. Change the specification document the change belongs to: `PRD.md`, `ARCHITECTURE.md`, a module `FRD.md`, or `ROADMAP.md`.
2. Update the owning module's `BACKLOG.md` row in the same pull request, so a merged fix never leaves a stale row.
3. Keep the reference links in `AGENTS.md` (`## Related Documents`) pointing at files that exist.

## Quality Verification & PR Process

```bash
bash scripts/ci.sh
```

Success is the final message `All 7 gates passed — ready to merge`. The script runs formatting and lint checks, type checking, a security scan, architecture checks, template hygiene, and tests.

To mirror the CI test job directly:

```bash
python -m pytest tests/ modules/shared/tests/ modules/cli/tests/ modules/mcp/tests/ modules/prompt/tests/ modules/session/tests/ modules/jobs/tests/ modules/browser/tests/ modules/config/tests/ modules/logging/tests/ modules/swarm/tests/ modules/update/tests/ --ignore=tests/test_e2e_pipeline.py -m "not benchmark" -v
```

Success is a pytest passed summary and exit status 0. Tests requiring a live authenticated Qwen session are excluded from this command.

Open the pull request only after the gates pass. In its description, explain the problem, the approach, and the verification commands you ran. Do not include Qwen sessions, secrets, generated browser data, build outputs, or personal configuration.