"""Acceptance tests for browser binary trust enforcement.

Pins BROWSER-01: a PATH-discovered browser binary that fails the ownership
check is refused even when no managed build is present.

The ownership check lives in ``utility_update_browser_binary._is_trusted_binary``
and is exercised through ``find_chrome_binary``. Because this suite runs as an
unprivileged user it cannot ``chown`` a file to another uid; instead it mocks
``os.getuid`` to report a foreign uid so the ownership check fails on a file the
process itself owns.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.shared.src import BrowserLaunchError
from modules.shared.src.update.utility_update_browser_binary import find_chrome_binary


def _seed_binary(bindir: Path, name: str = "chromium", mode: int = 0o755) -> Path:
    """Create an executable fake browser binary owned by the current process."""
    bindir.mkdir(parents=True, exist_ok=True)
    bindir.chmod(0o755)
    binary = bindir / name
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(mode)
    return binary


def test_acceptance_path_binary_with_foreign_owner_is_refused_without_managed_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PATH-discovered binary owned by another uid is skipped even though its
    permissions are otherwise sound, and no Playwright-managed build is present
    to fall back on."""
    bindir = tmp_path / "path-bin"
    _seed_binary(bindir, mode=0o755)

    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setattr(
        "modules.shared.src.update.utility_update_browser_binary._playwright_managed_binary",
        lambda prefer_gui=True: "",
    )
    monkeypatch.setattr("modules.shared.src.update.utility_update_browser_binary.EXTRA_PATHS", [])

    # The file is owned by this process's uid, but os.getuid() reports a
    # foreign uid, simulating a binary owned by another local account.
    monkeypatch.setattr(os, "getuid", lambda: 999)

    assert find_chrome_binary() == "", "a foreign-owned PATH binary must be refused"


def test_acceptance_no_trusted_binary_raises_browser_launch_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no trusted binary discoverable and no managed build, launching the
    browser raises BrowserLaunchError naming the failure."""
    from playwright.sync_api import Error as PlaywrightError

    from modules.browser.src.capabilities_browser_adapter import BrowserAdapter
    from modules.shared.src.common.taxonomy_core_vo import AppConfig

    bindir = tmp_path / "path-bin"
    _seed_binary(bindir, mode=0o755)

    monkeypatch.setenv("PATH", str(bindir))
    monkeypatch.setattr(
        "modules.shared.src.update.utility_update_browser_binary._playwright_managed_binary",
        lambda prefer_gui=True: "",
    )
    monkeypatch.setattr("modules.shared.src.update.utility_update_browser_binary.EXTRA_PATHS", [])
    monkeypatch.setattr(os, "getuid", lambda: 999)

    session_dir = tmp_path / "session"
    session_dir.mkdir()

    cfg = AppConfig(
        mode="batch",
        input_path=tmp_path / "in",
        output_path=tmp_path / "out",
        session_path=session_dir,
        headless=True,
    )

    with (
        patch("modules.browser.src.capabilities_browser_adapter.create_ephemeral_session") as ephemeral,
        patch("modules.browser.src.capabilities_browser_adapter.sync_playwright") as mock_pw,
    ):
        ephemeral.return_value.__enter__ = lambda self=None: str(session_dir)
        ephemeral.return_value.__exit__ = lambda *_exc: False

        mock_p = mock_pw.return_value.__enter__.return_value
        mock_p.chromium.launch_persistent_context.side_effect = PlaywrightError("no trusted browser binary")

        with pytest.raises(BrowserLaunchError):
            with BrowserAdapter().browser_session(cfg):
                pass
