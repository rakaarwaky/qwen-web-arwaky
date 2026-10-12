# BACKLOG — CLI Surface

Feature prefix: `CLIC-`. Last Updated: **2026-10-12**.

State and Health vocabulary, verification requirements, ownership rules, and ID
policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions)
and [Status Policy](../../ROADMAP.md#status-policy).

## Current Condition

- Done: CLI commands and controllers ship under `modules/cli/src`; the TUI
  layer is isolated in `modules/tui` and depends on this surface, never the
  reverse.
- In Progress: None.
- Blocked: None.
- Next: `CLIC-01`.

## Scenario Evidence

| Scenario | Evidence | Status |
|---|---|---|
| Non-interactive command flows | `modules/cli/tests/` unit + integration runs in CI | Pass |
| CLI never imports TUI at module load | Deferred import in `surface_cli_interactive_controller.run()`; `grep modules.tui modules/cli/src` shows only that site | Pass |

## Blockers

None.

## Release Readiness

Feature is release-ready pending the items in the Backlog section below.

## Deferred

None.

## Change Log

| Date | Change |
|---|---|
| 2026-10-12 | Split TUI layer into `modules/tui`; CLI keeps command controllers and doctor/sessions/jobs/swarm/update surfaces |

## Backlog

| ID | Item | Priority | State | Health | Owner | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|---|
| CLIC-01 | Track CLI-only surface issues (commands, controllers, doctor/sessions) here; TUI items live in `modules/tui/BACKLOG.md` | P2 | Ready | On Track | — | TUI split landed on `refactor/separate-cli-tui-modules`; no CLI-surface findings open at split time. | Move any CLI-specific finding into a new row with issue links and verification commands. | 2026-10-12 |

## Dependencies and Exit Evidence

- CLI surface depends on Root containers (`modules/root_core_container.py`,
  `modules/root_cli_main_entry.py`) for orchestrator wiring.
- A row can become Done only with the exact verification command, its result,
  and the implementing commit recorded in `Actual Condition`.
