# BACKLOG — Textual TUI Surface

Feature prefix: `TUI-`. Last Updated: **2026-10-21**.

State vocabulary, verification requirements, ownership rules, and ID policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions) and [Status Policy](../../ROADMAP.md#status-policy).

## Current Condition

- Done: `uv run python -m pytest modules/tui/tests/ -m "not benchmark"` reports **138 passed** (15 test files) on branch `rakaarwaky/ux-tui-cli-surface`, 2026-10-21.
- In Progress: None.
- Blocked: None.
- Next: `TUI-01`, `TUI-02`, `TUI-03`, `TUI-04`.

## Scenario Evidence

| Scenario | Evidence | Status |
|---|---|---|
| TUI compose tree, slot tabs, modals | `uv run python -m pytest modules/tui/tests/unit_surface_tui_app.py modules/tui/tests/unit_tui_modal_layout.py modules/tui/tests/unit_tui_confirm_modal_layout.py -m "not benchmark"` — 29 passed on commit `73aee43` | Pass |
| TUI log containment across terminal resizes | `uv run python -m pytest modules/tui/tests/unit_tui_log_containment.py -m "not benchmark"` — 34 passed on commit `73aee43` | Pass |
| TUI toast region and click guards | `uv run python -m pytest modules/tui/tests/unit_tui_toast_region_crash.py modules/tui/tests/unit_tui_handlers.py -m "not benchmark"` — 9 passed on commit `73aee43` | Pass |
| TUI session action button wiring | `uv run python -m pytest modules/tui/tests/unit_tui_session_action_buttons.py modules/tui/tests/unit_tui_add_session_button_wiring.py -m "not benchmark"` — 13 passed on commit `73aee43` | Pass |
| UX remediation regressions (glyphs, locale gate, pane-gated keys, empty-state hint, verdict ACTION lines, retry guidance, carousel tiers, key-hint strip, Swarm START/RESTART) | `uv run python -m pytest modules/tui/tests/unit_tui_ux_remediation.py -m "not benchmark"` — 25 passed on `rakaarwaky/ux-tui-cli-surface`, 2026-10-21 | Pass |
| Session-row button glyphs, tooltips, and the delete path | `uv run python -m pytest modules/tui/tests/unit_tui_session_action_buttons.py -m "not benchmark"` — 10 passed on `rakaarwaky/ux-tui-cli-surface`, 2026-10-21 | Pass |

## Blockers

None.

## Release Readiness

Surface is release-ready pending the items in the Backlog section below.

## Deferred

None.

## Change Log

| Date | Change |
|---|---|
| 2026-10-21 | UX remediation: 138 passed (15 test files); added `unit_tui_ux_remediation.py` (25 tests) and re-verified `unit_tui_session_action_buttons.py` (10 passed) |
| 2026-10-18 | Reworked this file to the aes-docs BACKLOG template: `TUI-` prefix, nine-column table, evidence-backed Done row, per-scenario commands and counts |

## Backlog

| ID | Item | Priority | State | Owner | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|
| TUI-01 | Ship the five shipped screens: Overview, Sessions, per-slot Chat, Swarm, and Settings under one token system | P1 | Done | — | `uv run python -m pytest modules/tui/tests/ -m "not benchmark"` — 138 passed, 0 failed on `rakaarwaky/ux-tui-cli-surface`, 2026-10-21; compose tree in `surface_tui_compose_layout.py`, tokens in `surface_tui_css_view.py`. | Record a released version containing `modules/tui` via `gh release view` and update this row to Released. | 2026-10-21 |
| TUI-02 | TUI modal layout and toast-region crash guard | P1 | Done | — | `uv run python -m pytest modules/tui/tests/unit_tui_modal_layout.py modules/tui/tests/unit_tui_confirm_modal_layout.py modules/tui/tests/unit_tui_toast_region_crash.py -m "not benchmark"` — 10 passed, 0 failed on commit `73aee43`. | Verify the toast crash guard against the next Textual upgrade. | 2026-10-18 |
| TUI-03 | TUI visual and interaction contract for designers and surface engineers | P1 | In Progress | — | `DESIGN.md` (this folder) is reworked to the aes-docs DESIGN contract; the token map cites the root `DESIGN.md` palette and `modules/tui/src/surface_tui_css_view.py` as the single source of truth. | Close this row when `DESIGN.md` passes `lint-arwaky-cli docs modules/tui` at Total: 0 in a release PR. | 2026-10-18 |
| TUI-04 | TUI log containment: the log panel keeps its height on every terminal size | P1 | Done | — | `uv run python -m pytest modules/tui/tests/unit_tui_log_containment.py -m "not benchmark"` — 34 passed, 0 failed on commit `73aee43`. | No action; monitor for regressions in future Textual releases. | 2026-10-18 |

## Dependencies and Exit Evidence

- TUI depends on the Root containers (`modules/root_cli_main_entry.py`) for orchestrator wiring; the TUI module never imports CLI code.
- A row can become Done only with the exact verification command, its pass/fail counts, and the implementing commit recorded in `Actual Condition`. `Done` evidence lives on the `Actual Condition` cell of the row above.
