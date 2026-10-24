# BACKLOG — Textual TUI Surface

Feature prefix: `TUI-`. Last Updated: **2026-10-24**.

State vocabulary, verification requirements, ownership rules, and ID policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions) and [Status Policy](../../ROADMAP.md#status-policy).

## Current Condition

- Done: `uv run python -m pytest modules/tui/tests/ -m "not benchmark"` reports **138 passed** (15 test files) on branch `rakaarwaky/ux-tui-cli-surface`, 2026-10-21.
- In Progress: `TUI-01` release evidence recording.
- Next: `TUI-01`.

## Scenario Evidence

| Scenario | Kind | Test file | Test name | Last verified |
|---|---|---|---|---|
| TUI compose tree, slot tabs, modals | Automated | `modules/tui/tests/unit_surface_tui_app.py` `modules/tui/tests/unit_tui_modal_layout.py` `modules/tui/tests/unit_tui_confirm_modal_layout.py` | all tests | `73aee43` (29 passed) |
| TUI log containment across terminal resizes | Automated | `modules/tui/tests/unit_tui_log_containment.py` | all tests | `73aee43` (34 passed) |
| TUI toast region and click guards | Automated | `modules/tui/tests/unit_tui_toast_region_crash.py` `modules/tui/tests/unit_tui_handlers.py` | all tests | `73aee43` (9 passed) |
| TUI session action button wiring | Automated | `modules/tui/tests/unit_tui_session_action_buttons.py` `modules/tui/tests/unit_tui_add_session_button_wiring.py` | all tests | `73aee43` (13 passed) |
| UX remediation regressions (glyphs, locale gate, pane-gated keys, empty-state hint, verdict ACTION lines, retry guidance, carousel tiers, key-hint strip, Swarm START/RESTART) | Automated | `modules/tui/tests/unit_tui_ux_remediation.py` | all tests | `rakaarwaky/ux-tui-cli-surface`, 2026-10-21 (25 passed) |
| Session-row button glyphs, tooltips, and the delete path | Automated | `modules/tui/tests/unit_tui_session_action_buttons.py` | all tests | `rakaarwaky/ux-tui-cli-surface`, 2026-10-21 (10 passed) |

## Blockers

None.

## Release Readiness

| Area | Status | Notes |
|---|---|---|
| Tests | Done | 138 passed on branch `rakaarwaky/ux-tui-cli-surface`, 2026-10-21 |
| Scenario evidence | Done | 6 scenarios mapped in Scenario Evidence |
| Docs | Done | `DESIGN.md` reworked to the aes-docs DESIGN contract; `uv run lint-arwaky-cli docs modules/tui` reports no DESIGN.md findings at this commit |
| Backlog items | In Progress | TUI-01 pending release recording |

## Deferred

None.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-10-25 | TUI-03 DESIGN.md rework closed (lint evidence at `a00c66a`); TUI-03 removed from In Progress/Next, only `TUI-01` release evidence remains open. | @qwen-web-arwaky |
| 2026-10-24 | TUI-03 Done: `DESIGN.md` reworked to the aes-docs DESIGN contract; `uv run lint-arwaky-cli docs modules/tui` reports 0 DESIGN.md findings at `a00c66a` | @rakaarwaky |
| 2026-10-21 | UX remediation: 138 passed (15 test files); added `unit_tui_ux_remediation.py` (25 tests) and re-verified `unit_tui_session_action_buttons.py` (10 passed) | @rakaarwaky |
| 2026-10-18 | Reworked this file to the aes-docs BACKLOG template: `TUI-` prefix, nine-column table, evidence-backed Done row, per-scenario commands and counts | @rakaarwaky |

## Backlog

| ID | Priority | State | Dependencies | Next Action | Updated |
|---|---|---|---|---|---|
| TUI-01 | P1 | Done | Ship the five shipped screens: Overview, Sessions, per-slot Chat, Swarm, and Settings under one token system. `uv run python -m pytest modules/tui/tests/ -m "not benchmark"` — 138 passed, 0 failed on `rakaarwaky/ux-tui-cli-surface`, 2026-10-21; compose tree in `surface_tui_compose_layout.py`, tokens in `surface_tui_css_view.py`. | Record a released version containing `modules/tui` via `gh release view` and attach the release evidence to this row. | 2026-10-21 |
| TUI-02 | P1 | Done | TUI modal layout and toast-region crash guard. `uv run python -m pytest modules/tui/tests/unit_tui_modal_layout.py modules/tui/tests/unit_tui_confirm_modal_layout.py modules/tui/tests/unit_tui_toast_region_crash.py -m "not benchmark"` — 10 passed, 0 failed on commit `73aee43`. | Verify the toast crash guard against the next Textual upgrade. | 2026-10-18 |
| TUI-03 | P1 | Done | TUI visual and interaction contract for designers and surface engineers. `DESIGN.md` (this folder) is reworked to the aes-docs DESIGN contract: aligned `## Brand & Style` / `## Components` / `## Reference` H2s matching the sibling surface DESIGN docs, a token map that cites the root `DESIGN.md` palette table and `modules/tui/src/surface_tui_css_view.py` (`_COLORS` / `THEME` / `SEMANTIC_ALIASES`) as the single source of truth. `uv run lint-arwaky-cli docs modules/tui` — 0 DESIGN.md findings at commit `a00c66a`, 2026-10-24. | No action; keep the token map in step with `surface_tui_css_view.py` in the same commit when a value changes. | 2026-10-24 |
| TUI-04 | P1 | Done | TUI log containment: the log panel keeps its height on every terminal size. `uv run python -m pytest modules/tui/tests/unit_tui_log_containment.py -m "not benchmark"` — 34 passed, 0 failed on commit `73aee43`. | No action; monitor for regressions in future Textual releases. | 2026-10-18 |

## Dependencies and Exit Evidence

- TUI depends on the Root containers (`modules/root_cli_main_entry.py`) for orchestrator wiring; the TUI module never imports CLI code.
- A row can become Done only with the exact verification command, its pass/fail counts, and the implementing commit recorded in `Dependencies`. `Done` evidence lives on the `Dependencies` cell of the row above.
