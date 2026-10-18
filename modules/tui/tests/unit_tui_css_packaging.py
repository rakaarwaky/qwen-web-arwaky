"""Regression tests for TUI CSS asset discovery and packaging metadata.

Ensures that the modular CSS stylesheets referenced by ``surface_tui_css_view``
exist on disk and that ``pyproject.toml`` includes them in ``tool.setuptools.package-data``
so wheels and installed environments bundle them.
"""

from __future__ import annotations

from pathlib import Path

from modules.tui.src.surface_tui_css_view import _CSS_DIR, TUI_CSS

_REQUIRED_CSS_FILES = [
    "surface_tui_css_component.css",
    "surface_tui_css_layout.css",
    "surface_tui_css_modal.css",
    "surface_tui_css_screen.css",
]


def test_tui_css_files_exist_and_non_empty() -> None:
    """Every modular CSS fragment must exist in the TUI src directory."""
    for filename in _REQUIRED_CSS_FILES:
        css_path = _CSS_DIR / filename
        assert css_path.is_file(), f"Missing required CSS asset: {css_path}"
        content = css_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, f"CSS asset {filename} is empty"


def test_tui_css_combined_stylesheet_assembly() -> None:
    """TUI_CSS must contain token headers and rules from all CSS fragments."""
    assert "Obsidian Terminal Design Tokens" in TUI_CSS
    assert "Screen {" in TUI_CSS
    assert ".app-brand-row" in TUI_CSS
    assert "layers: base modal;" in TUI_CSS


def test_pyproject_package_data_declares_tui_css() -> None:
    """pyproject.toml must declare package-data for modules.tui.src."""
    repo_root = Path(__file__).resolve().parents[3]
    pyproject_path = repo_root / "pyproject.toml"
    assert pyproject_path.is_file(), f"pyproject.toml not found at {pyproject_path}"

    content = pyproject_path.read_text(encoding="utf-8")
    assert '"modules.tui.src" = ["*.css"]' in content
