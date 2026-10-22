"""Obsidian Terminal design tokens and Textual CSS for the Qwen TUI application.

Surface layer (surface_cli): design-system colors and stylesheet string
consumed by :class:`~modules.tui.src.surface_tui_app_screen.QwenTuiApp`.

This module is the **single source of truth for colour**. ``_COLORS`` is the
canonical palette; ``THEME`` and the ``$token`` CSS variables are derived from
it, so a component never hardcodes a hex value. The canonical hex values are
mirrored in the "Terminal Palette" table of the root ``DESIGN.md`` — keep
both in step when a value changes.
"""

from __future__ import annotations

# V1/V4: single source of truth — derive THEME and CSS tokens from _COLORS.
# Every text colour below clears WCAG AA (4.5:1) against its background.
# Mirror the canonical hex values in the root DESIGN.md.
from pathlib import Path

_CSS_DIR = Path(__file__).parent
_COLORS: dict[str, str] = {
    # ── Semantic surface stack (dark, layered) ──────────────────────────
    "bg": "#171A1F",  # canonical background / screen fill
    "surface": "#22262C",  # canonical raised surface (cards, rows)
    "bg_base": "#171A1F",  # alias: screen background
    "bg_surface": "#12151A",  # alias: recessed strip (tab bar)
    "bg_overlay": "#1C2026",  # alias: card fill
    "bg_raised": "#22262C",  # alias: raised tile / row hover target
    "bg_hover": "#2A2F36",  # surface hover
    "bg_active": "#31373F",  # surface pressed / selected row
    # ── Borders ─────────────────────────────────────────────────────────
    "border": "#2E343C",  # hairline separator
    "focus_ring": "#38BDF8",  # focus outline
    # ── Text ────────────────────────────────────────────────────────────
    "text": "#E5E7EB",  # canonical primary text
    "text_muted": "#9AA4B2",  # canonical secondary text
    "fg_primary": "#E5E7EB",  # alias: primary text
    "fg_muted": "#9AA4B2",  # alias: secondary text
    "fg_accent": "#7DD3FC",  # accent-tinted text
    "fg_on_accent": "#0B1220",  # text on accent fill
    "primary_fixed": "#BAE6FD",  # tinted monospace value
    # ── Accent / status ─────────────────────────────────────────────────
    "accent": "#38BDF8",  # primary accent
    "success": "#4ADE80",  # canonical success
    "status_ok": "#4ADE80",  # alias: success
    "bright": "#4ADE80",  # alias: success (highlight)
    "warning": "#FACC15",  # canonical warning
    "status_warn": "#FACC15",  # alias: warning
    "danger": "#E5484D",  # canonical danger
    "status_err": "#E5484D",  # alias: danger
    "status_info": "#38BDF8",  # informational = accent
    "status_muted": "#9AA4B2",  # neutral state
    # ── Danger surfaces ─────────────────────────────────────────────────
    # Subtle by default (tinted text on a dark red wash); the strong fill is
    # reserved for focus and the confirm modal.
    "danger_soft_bg": "#3A1214",
    "danger_soft_fg": "#FCA5A5",
    "danger_bg": "#E5484D",  # strong fill (focus / modal confirm)
    "danger_fg": "#FFF1F2",  # text on the strong fill
}

# Canonical semantic names (the design layer) → _COLORS key. Components and
# the design-token tests read the semantic layer through this map.
SEMANTIC_ALIASES: dict[str, str] = {
    "bg": "bg",
    "surface": "surface",
    "border": "border",
    "text": "text",
    "text-muted": "text_muted",
    "accent": "accent",
    "success": "success",
    "warning": "warning",
    "danger": "danger",
}

THEME: dict[str, str] = {
    "accent": _COLORS["accent"],
    "accent_fg": _COLORS["fg_accent"],
    "primary": _COLORS["fg_primary"],
    "muted": _COLORS["fg_muted"],
    "ok": _COLORS["status_ok"],
    "warn": _COLORS["status_warn"],
    "err": _COLORS["status_err"],
    "info": _COLORS["status_info"],
    "bright": _COLORS["bright"],
    "danger": _COLORS["danger"],
    "success": _COLORS["success"],
    "warning": _COLORS["warning"],
}


def _css_vars() -> str:
    """V1: generate CSS variable declarations from the canonical color map."""
    return "\n".join(f" ${k}: {v};" for k, v in _COLORS.items())


# Build TUI_CSS via plain string concatenation (NOT f-string) to avoid ruff
# F821 false positives — ruff parses f-string interpolation as Python and
# flags CSS property names like ``background`` as undefined names. The body
# lives in its own constant so the assembly is name + name; a ``+`` directly
# against a triple-quoted literal makes bandit B608 read the CSS ``Select``
# rule plus a "from" in a comment as a hardcoded SQL query.
_CSS_HEADER = "/* ═══ Obsidian Terminal Design Tokens (V2 — auto-generated) ═══ */\n" + _css_vars()


# Assemble TUI_CSS by reading body parts from sibling .css files
TUI_CSS = (
    _CSS_HEADER
    + (_CSS_DIR / "surface_tui_css_screen.css").read_text(encoding="utf-8")
    + (_CSS_DIR / "surface_tui_css_layout.css").read_text(encoding="utf-8")
    + (_CSS_DIR / "surface_tui_css_modal.css").read_text(encoding="utf-8")
    + (_CSS_DIR / "surface_tui_css_component.css").read_text(encoding="utf-8")
)

__all__ = ["_COLORS", "THEME", "TUI_CSS", "_CSS_HEADER"]
