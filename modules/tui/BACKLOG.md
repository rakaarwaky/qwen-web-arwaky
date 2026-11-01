# BACKLOG — Textual TUI Surface

Feature prefix: `TUI-`. Last Updated: 2026-10-25.

DESIGN: [DESIGN.md](DESIGN.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).

## Progress Overview

The TUI surface is Done. `uv run python -m pytest modules/tui/tests/ -m "not benchmark" -q` → 175 passed (commit `2152c8a`, 2026-10-25); `DESIGN.md` is reworked to the aes-docs DESIGN contract and reports 0 findings. No row is in progress or blocked; every entry is Done.

## Backlog Status

### DS-TUI-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | The theme is read through `THEME` in `modules/tui/src/surface_tui_css_view.py` (`_COLORS` / `THEME` / `SEMANTIC_ALIASES`); no raw hex lives in a widget. Verified `uv run lint-arwaky-cli docs modules/tui` → 0 DESIGN.md findings at commit `a00c66a`; `uv run python -m pytest modules/tui/tests/ -m "not benchmark" -q` → 175 passed (commit `2152c8a`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-TUI-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Root type stops projected onto terminal attributes (weight, case, width, emphasis): `headline-*` → `.app-brand-title`, `.card-title`; `body-*` → `QwenTuiRichLog` stream; `label-*` → `.session-cell-status`, metric tile labels (JetBrains Mono). Verified `uv run python -m pytest modules/tui/tests/ -m "not benchmark" -q` → 175 passed (commit `2152c8a`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-TUI-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Layout regions implemented: brand row, `TabbedContent` panes (Overview, Sessions, Slot 1…N Chat, Swarm, Settings), and docked nav dock. Verified `uv run python -m pytest modules/tui/tests/unit_surface_tui_app.py -v` → compose tree passes (commit `73aee43`, 29 passed). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-TUI-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Session-row actions render `↻` / `☐` / `×` with ASCII fallbacks `r` / `h` / `x` under the `_unicode_ok` gate; shipped labels come from `_GLYPHS` in `surface_tui_utils_component.py`; `NO_COLOR=1` never gates iconography (UX-2-001). Verified `uv run python -m pytest modules/tui/tests/unit_tui_session_action_buttons.py -v` → 10 passed (commit `73aee43`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-TUI-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Cards render screen-card headline, metric tiles, body rows with status beacons, trailing action clusters, and state layer beacons or muted placeholders. Verified `uv run python -m pytest modules/tui/tests/ -m "not benchmark" -q` → 175 passed (commit `2152c8a`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-TUI-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `notify()` toasts anchor above the nav dock, never block input, clicks guarded; pickers (`FilePickerModal`, `TemplatePickerModal`, `AddSessionModal`, `ConfirmModal`, `HelpScreen`) ship. Verified `uv run python -m pytest modules/tui/tests/unit_tui_toast_region_crash.py modules/tui/tests/unit_tui_handlers.py -v` → 9 passed (commit `73aee43`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-TUI-007

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Global bindings from `QwenTuiApp.BINDINGS` (`alt+0..9`, `ctrl+alt+0..9`, `enter`, `ctrl+x`, `ctrl+l`, `ctrl+q`, `?`, `a`, `r/e/d`, etc.); one focused widget at a time, focus ring is `accent`, modals capture and restore focus. Verified `uv run python -m pytest modules/tui/tests/unit_tui_handlers.py -v` (commit `73aee43`). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### DS-TUI-008

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | Empty/error states: `session-empty` placeholder row, idle-slot `● READY` badge, swarm `swarm-file-name` reads "No file attached", `danger` FAILED envelope, `warning` EXPIRED badge. Verified `uv run python -m pytest modules/tui/tests/unit_tui_log_containment.py -m "not benchmark"` → 34 passed (commit `73aee43`). |
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
| Root Design | Obsidian Terminal theme (palette, type, spacing) | [DESIGN.md](../../DESIGN.md) |
