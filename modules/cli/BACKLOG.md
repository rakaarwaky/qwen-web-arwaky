# BACKLOG — CLI Surface

DESIGN: [DESIGN.md](DESIGN.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-25

## Progress Overview

The CLI surface is Done. `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (2026-10-25, commit `02e54b7`) confirms the surface boundary partition with no CLI-only surface findings open. No row is in progress or blocked; every backlog entry is Done.

## Backlog Status

### DS-CLI-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/cli/tests/smoke_entry_points.py -v` → covers stdout human-readable reports and stderr warnings; `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (2026-10-25, commit `02e54b7`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-CLI-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/cli/tests/smoke_entry_points.py -v` → `test_cli_entry_runs_help`, `test_cli_command_tree_is_grouped`, `test_legacy_flat_commands_are_rejected`, `test_cli_barrel_re_exports_every_surface`; command surfaces platform the shared failure envelope. Evidence `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (commit `02e54b7`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-CLI-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Exit codes mapped from envelopes: `0` success, `1` failure, `2` argparse usage, `3` `AuthRequiredError`, `130` `KeyboardInterrupt`, verified via `utility_core_exit.exit_code_for` and `root_cli_main_entry._exit_code_for_result`. Evidence `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (commit `02e54b7`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-CLI-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Every non-interactive command returns a standard envelope from `utility_response_normalizer` (`success_response` / `error_response`); `--json` prints the envelope verbatim on stdout. Covered by `contract_json_envelope.py`. Evidence `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (commit `02e54b7`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-CLI-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Error codes pinned: `cli-400` validation, `cli-422` processing, `cli-429` saturated pool, `cli-500` unhandled, `cli-502` update-specific, `auth-required`. Verified `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (commit `02e54b7`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-CLI-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Shared flags `--json`, `--headless`/`--no-headless`, `-o FILE`, `--deep` registered on the shared parent parser for every `prompt`/`job`/`swarm`/`observability`/`session` group subcommand. Verified `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (commit `02e54b7`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-CLI-007

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Status glyphs `STATUS_GLYPHS` declared in the shared Taxonomy layer (`modules/shared/src/common/taxonomy_core_constant.py`) and re-exported by `surface_cli_json_hook` (UX-3-002); CLI and TUI cannot drift apart. Verified `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed (commit `02e54b7`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals and scope | [PRD.md](../../PRD.md) |
| DESIGN | Surface specification | [DESIGN.md](DESIGN.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
