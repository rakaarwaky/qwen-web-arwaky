"""Extended tests for browser.py — browser_session, _launch_context."""

from __future__ import annotations

import stat
from unittest.mock import MagicMock, patch

import pytest

from modules.browser.src.capabilities_browser_adapter import BrowserAdapter
from modules.shared.src import AppConfig

_browser = BrowserAdapter()


class TestBrowserSession:
    def test_browser_session_dir_keeps_execute_bit(self, tmp_path):
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            session_path=tmp_path / "session",
            headless=True,
        )
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]

        with patch("modules.browser.src.capabilities_browser_adapter.sync_playwright") as mock_pw:
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx

            with _browser.browser_session(cfg):
                mode = cfg.session_path.stat().st_mode
                assert stat.S_ISDIR(mode)
                assert stat.S_IMODE(mode) == 0o700

    @pytest.mark.parametrize(
        "initial_mode",
        [0o644, 0o755],
        ids=["missing-execute-bit", "world-readable"],
    )
    def test_browser_session_repairs_existing_dir_permissions(self, tmp_path, initial_mode: int):
        """A pre-existing session dir with non-0700 perms is repaired to 0o700."""
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            session_path=tmp_path / "session",
            headless=True,
        )
        cfg.session_path.mkdir(parents=True, exist_ok=True)
        cfg.session_path.chmod(initial_mode)
        assert stat.S_IMODE(cfg.session_path.stat().st_mode) == initial_mode

        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]

        with patch("modules.browser.src.capabilities_browser_adapter.sync_playwright") as mock_pw:
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx

            with _browser.browser_session(cfg):
                mode = cfg.session_path.stat().st_mode
                assert stat.S_ISDIR(mode)
                assert stat.S_IMODE(mode) == 0o700

    def test_browser_session_headless(self, tmp_path):
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            session_path=tmp_path / "session",
            headless=True,
        )
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]

        with patch("modules.browser.src.capabilities_browser_adapter.sync_playwright") as mock_pw:
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx

            with _browser.browser_session(cfg) as ctx:
                assert ctx == mock_ctx
            mock_ctx.close.assert_called()

    def test_browser_session_filters_assets(self, tmp_path):
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            session_path=tmp_path / "session",
            headless=True,
        )
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]

        with patch("modules.browser.src.capabilities_browser_adapter.sync_playwright") as mock_pw:
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx

            with _browser.browser_session(cfg):
                mock_ctx.route.assert_called_once()

    def test_browser_session_login_mode_no_route(self, tmp_path):
        cfg = AppConfig(
            mode="login",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            session_path=tmp_path / "session",
            headless=False,
        )
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]

        with patch("modules.browser.src.capabilities_browser_adapter.sync_playwright") as mock_pw:
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx

            with _browser.browser_session(cfg):
                mock_ctx.route.assert_not_called()

    def test_browser_session_close_error_handled(self, tmp_path):
        from playwright.sync_api import Error

        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            session_path=tmp_path / "session",
            headless=True,
        )
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]
        mock_ctx.close.side_effect = Error("already closed")

        with patch("modules.browser.src.capabilities_browser_adapter.sync_playwright") as mock_pw:
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx

            with _browser.browser_session(cfg):
                pass


class TestLaunchContext:
    def test_retries_on_failure(self):
        from playwright.sync_api import Error

        p = MagicMock()
        kwargs = {"user_data_dir": "", "headless": True}

        good_ctx = MagicMock()
        good_ctx.pages = [MagicMock()]

        call_count = [0]

        def launch_side_effect(**kw):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Error("crash")
            return good_ctx

        p.chromium.launch_persistent_context.side_effect = launch_side_effect

        ctx = BrowserAdapter()._launch_context(p, kwargs)
        assert ctx == good_ctx

    def test_cleans_stale_locks(self, tmp_path):
        p = MagicMock()
        lock_dir = tmp_path / "session"
        lock_dir.mkdir()
        (lock_dir / "SingletonLock").write_text("lock")
        (lock_dir / "SingletonSocket").write_text("socket")

        kwargs = {"user_data_dir": str(lock_dir), "headless": True}
        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx

        BrowserAdapter()._launch_context(p, kwargs)
        assert not (lock_dir / "SingletonLock").exists()
        assert not (lock_dir / "SingletonSocket").exists()
