# BACKLOG — CLI Surface

DESIGN: [DESIGN.md](DESIGN.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md) — do not redefine here.
Last Updated: 2026-10-24

## Current Condition

- Done: `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 178 passed on 2026-10-21 (branch `rakaarwaky/ux-tui-cli-surface`); `CLIC-01` closed Done — surface boundary partition confirmed, no CLI-only surface findings open as of 2026-10-24.
- In Progress: None.
- Next Action: None.

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated |
|---|---|---|---|---|---|
| CLIC-01 | P2 | Done | Track CLI-only surface issues (commands, controllers, doctor/sessions) here; TUI items live in `modules/tui/BACKLOG.md`. TUI split landed on `refactor/separate-cli-tui-modules`; no CLI-surface findings open at split time, so this row closes with no new rows needed. Verified: `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 197 passed, 0 failed on branch `rakaarwaky/cl01` (issue #671). | No action; open a new `CLIC-NN` row with issue links when a CLI-surface finding lands. | 2026-10-24 |

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| CLI entry point runs `--help` without error | Automated | `modules/cli/tests/smoke_entry_points.py` | `test_cli_entry_runs_help` | `73aee43` |
| CLI command tree is grouped correctly | Automated | `modules/cli/tests/smoke_entry_points.py` | `test_cli_command_tree_is_grouped` | `73aee43` |
| Legacy flat commands are rejected | Automated | `modules/cli/tests/smoke_entry_points.py` | `test_legacy_flat_commands_are_rejected` | `73aee43` |
| `prompt direct` uses pool session even with one member | Automated | `modules/cli/tests/unit_session_rotation_direct_prompt.py` | all tests | `73aee43` |
| CLI never imports TUI at module load | Automated | `modules/cli/tests/unit_surface_cli_controller.py` | all tests | `73aee43` |
| `session` group: list/status/health/remove JSON + login re-prompt loop | Automated | `modules/cli/tests/unit_surface_cli_sessions_command.py` | all tests | 2026-10-21 |
| `session remove` TTY confirmation (UX-4-003) | Automated | `modules/cli/tests/unit_surface_cli_sessions_command.py` | `test_remove_*` | 2026-10-21 |
| List table renders the full `⛔ auth_required` cell at 80 columns (UX-5-002) | Automated | `modules/cli/tests/unit_surface_cli_sessions_command.py` | `test_list_renders_full_auth_required_cells_at_80_columns` | 2026-10-21 |
| `session` and command surfaces platform the shared failure envelope | Automated | `modules/cli/tests/contract_json_envelope.py` | all tests | 2026-10-18 |
| `doctor` sandbox detection and `--deep` probe wiring | Automated | `modules/cli/tests/unit_surface_cli_doctor_sandbox.py` | all tests | 2026-10-18 |
| CLI barrel re-exports all ten surface modules | Automated | `modules/cli/tests/smoke_entry_points.py` | `test_cli_barrel_re_exports_every_surface` | 2026-10-18 |
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
| Tests | Done | `uv run python -m pytest modules/cli/tests/ -m "not benchmark" -v` → 176 passed on 2026-10-18 |
| Scenario evidence | Done | 14 of 14 scenarios mapped |
| Docs | Done | [DESIGN.md](DESIGN.md) is specification-only for the CLI surface. |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-12 | Split TUI layer into `modules/tui`; CLI keeps command controllers and doctor/sessions/jobs/swarm/update surfaces | @rakaarwaky |
| 2026-10-18 | Reworked BACKLOG.md to match aes-docs template: corrected section order, scenario evidence table format, release readiness table; re-based Done line on `73aee43` with 92-test count | @rakaarwaky |
| 2026-10-18 | v6.7.0: JSON envelope + `session --json`, doctor pool-only session check with `--deep`, iterative login re-prompt, rotation `[WARN]`, glyph/table helpers, barrel completion; test count 92 → 149; review rounds 1–3 closed on top (envelope contract, host-independent doctor fixture, run-surface failure pin, dead adapter removal, required session injection, `job cleanup` payload docs); count 149 → 176 at `b93d2ba` | @rakaarwaky |
| 2026-10-21 | UX remediation on `rakaarwaky/ux-tui-cli-surface`: shared `STATUS_GLYPHS` re-export (UX-3-002), `session remove` TTY confirmation (UX-4-003), and the UX-5-002 floor-of-16 regression in `unit_surface_cli_sessions_command.py`; count 176 → 178 verified this session | @rakaarwaky |
| 2026-10-24 | CLIC-01 closed Done: surface boundary partition confirmed (TUI items in `modules/tui/BACKLOG.md`); no CLI-only findings open; 197 tests re-verified on `rakaarwaky/cl01` (issue #671) | @rakaarwaky |
