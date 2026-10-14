"""Unit tests for the shared update subprocess security boundary."""

from __future__ import annotations

import sys

import pytest

from modules.shared.src.update.utility_update_pipeline import (
    SUBPROCESS_FORBIDDEN_CHARS,
    approved_spawn_command,
    run_subprocess,
)


def test_forbidden_characters_are_rejected() -> None:
    for char in SUBPROCESS_FORBIDDEN_CHARS:
        rc, _out, err = run_subprocess([sys.executable, "-m", "pip", f"bad{char}arg"])
        assert rc == 1
        assert "shell metacharacters" in err


@pytest.mark.parametrize("module", ["os", "subprocess"])
def test_unsupported_python_module_is_rejected(module: str) -> None:
    with pytest.raises(ValueError, match="Unsupported update command"):
        approved_spawn_command([sys.executable, "-m", module, "system"])


def test_pip_command_is_allowlisted() -> None:
    argv = [sys.executable, "-m", "pip", "--version"]
    assert approved_spawn_command(argv) == argv


def test_playwright_command_is_allowlisted() -> None:
    argv = [sys.executable, "-m", "playwright", "install", "chromium"]
    assert approved_spawn_command(argv) == argv


def test_other_python_module_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported update command"):
        approved_spawn_command([sys.executable, "-m", "os", "system"])
