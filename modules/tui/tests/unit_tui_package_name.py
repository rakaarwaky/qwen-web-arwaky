"""ARCH-4-002: TUI package must not collide with the root project name."""

from pathlib import Path


def test_tui_package_name_is_distinct() -> None:
    root = Path(__file__).resolve().parents[3]
    tui = (root / "modules" / "tui" / "pyproject.toml").read_text()
    main = (root / "pyproject.toml").read_text()
    assert 'name = "qwen-web-arwaky-tui"' in tui
    assert 'name = "qwen-web-arwaky"' in main
