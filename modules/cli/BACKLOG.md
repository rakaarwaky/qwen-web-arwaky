# BACKLOG — CLI Surface

DESIGN: [DESIGN.md](DESIGN.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State / Health: values from root [ROADMAP.md](../../ROADMAP.md) — do not redefine here.
Last Updated: 2026-10-18

## Current Condition

- Done: `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 92 passed, at `73aee43`, on 2026-10-18.
- In Progress: None.
- Blocked: None.
- Next Action: `CLIC-01`, track CLI-only surface issues as they surface.

## Backlog

| ID | Item | Priority | State | Health | Owner | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|---|
| CLIC-01 | Track CLI-only surface issues (commands, controllers, doctor/sessions) here; TUI items live in `modules/tui/BACKLOG.md` | P2 | Ready | On Track | — | TUI split landed on `refactor/separate-cli-tui-modules`; no CLI-surface findings open at split time. | Move any CLI-specific finding into a new row with issue links and verification commands. | 2026-10-18 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| CLI entry point runs `--help` without error | Automated | `modules/cli/tests/smoke_entry_points.py` | `test_cli_entry_runs_help` | `73aee43` |
| CLI command tree is grouped correctly | Automated | `modules/cli/tests/smoke_entry_points.py` | `test_cli_command_tree_is_grouped` | `73aee43` |
| Legacy flat commands are rejected | Automated | `modules/cli/tests/smoke_entry_points.py` | `test_legacy_flat_commands_are_rejected` | `73aee43` |
| `prompt direct` uses pool session even with one member | Automated | `modules/cli/tests/unit_session_rotation_direct_prompt.py` | all tests | `73aee43` |
| CLI never imports TUI at module load | Automated | `modules/cli/tests/unit_surface_cli_controller.py` | all tests | `73aee43` |
| `doctor` command runs successfully | Automated | `modules/cli/tests/unit_surface_cli_controller.py` | `test_doctor_command` | `73aee43` |
| Jobs surface handles submit/status/list/cleanup | Automated | `modules/cli/tests/unit_surface_cli_jobs_command.py` | all tests | `73aee43` |
| Observability surface handles report/status | Automated | `modules/cli/tests/unit_surface_cli_observability_command.py` | all tests | `73aee43` |
| Swarm surface handles start/status/cancel | Automated | `modules/cli/tests/unit_surface_cli_swarm_command.py` | all tests | `73aee43` |
| Update surface handles check/rollback | Automated | `modules/cli/tests/unit_surface_cli_update_command.py` | all tests | `73aee43` |

## Blockers

None.

## Dependencies

- CLI surface depends on Root containers (`modules/root_cli_main_entry.py`, `modules/root_mcp_container.py`) for orchestrator wiring.
- A row can become `Done` only with the exact verification command, its result, and the implementing commit recorded in `Actual Condition`.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 92 passed at `73aee43` |
| Scenario evidence | Done | 10 of 10 scenarios mapped |
| Docs | Done | [DESIGN.md](DESIGN.md) is specification-only for the CLI surface. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-12 | Split TUI layer into `modules/tui`; CLI keeps command controllers and doctor/sessions/jobs/swarm/update surfaces | @rakaarwaky |
| 2026-10-18 | Reworked BACKLOG.md to match aes-docs template: corrected section order, scenario evidence table format, release readiness table; re-based Done line on `73aee43` with 92-test count | @rakaarwaky |
