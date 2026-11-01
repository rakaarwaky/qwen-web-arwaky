# Contributing

## Contribution Overview

Contribute to qwen-web-arwaky as a focused, test-first change: one problem, one pull request, one owning module under `modules/`. Read [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md](ARCHITECTURE.md) before touching code — the 7-layer rules and naming contract are enforced in CI at zero violations. A change is not done until the local gates below pass and the PR description names the evidence that proves it.

## Contribution Guidelines

- **Editable installation is forbidden.** The runtime must never execute from the repository source tree. All local development and testing uses an immutable `uv`-managed venv (`export UV_PROJECT_ENVIRONMENT="$PWD/.venv" && uv sync`); `pip install -e .` is rejected on review.
- **Every code change ships its own test.** The test exercises the behavior, not the implementation. For a regression, add a minimal repro that fails before the fix and passes after.
- **Keep module boundaries intact.** Files land in the vertical slice of the owning feature module; no cross-feature import shortcuts. If a change spans two modules, the root container wires it once.
- **Update the spec in the same PR.** A behavior change updates the owning `FRD.md` or `DESIGN.md` and the module's `BACKLOG.md` row in the same commit.
- **Never commit runtime data.** Generated responses, browser profiles, session files, and personal config stay out of the diff.

## Workflow

| Step | Action | Detail |
|------|--------|--------|
| 1 | Pick the owning module | Read the module's `FRD.md`/`DESIGN.md` + `BACKLOG.md`; confirm the change belongs in that vertical slice |
| 2 | Write a failing test | One focused test per behavior; run it to confirm the red |
| 3 | Implement the fix | Keep the change inside the owning module; wire cross-module dependencies only through the root containers |
| 4 | Update the spec | Refresh the `FRD.md`/`DESIGN.md` and the `BACKLOG.md` row in the same commit |
| 5 | Run the local gates | `bash scripts/ci.sh` — must end with `All 7 gates passed`; this runs formatting, lint, type, security, architecture, template-hygiene, and the full test selection |
| 6 | Open the PR | Description names the problem, the approach, and the verification command; no runtime data, no secrets, no personal paths |
| 7 | CI + review | `ci.yml` (format, lint, lock drift, build, test, self-lint) and architecture review must pass before merge |
| 8 | Merge | Squash merge into `main`; the auto-merge workflow handles the queue |

## Commit Convention

| Type | Usage | Example |
|------|-------|---------|
| `feat` | New behavior, new module capability | `feat(prompt): add extraction verdict to response payload` |
| `fix` | Bug fix, regression repair | `fix(session): close leaked Chromium context on probe timeout` |
| `refactor` | Behavior-preserving restructure | `refactor(config): move post-update smoke gate into capabilities_config_health_probe` |
| `test` | Test or fixture changes only | `test(browser): add selector-regression lock for the new DOM` |
| `docs` | Spec or doc update, no code change | `docs(ROADMAP): advance TUI-01 to Done with release evidence` |
| `chore` | Build, deps, CI config, lockfile | `chore: bump playwright to 1.62.0 and regenerate uv.lock`

## Reference

| Artifact | Purpose | Link |
|----------|---------|------|
| PRD | Product scope, requirements, and success metrics | [PRD.md](PRD.md) |
| ARCHITECTURE | Layer boundaries and allowed dependencies | [ARCHITECTURE.md](ARCHITECTURE.md) |
| ROADMAP | What ships next, in order | [ROADMAP.md](ROADMAP.md) |
| TEST | Test strategy, markers, and fixture conventions | [TEST.md](TEST.md) |
| AGENTS | Agent operating guide, command gates | [AGENTS.md](AGENTS.md) |