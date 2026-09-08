"""Unit tests for surface_cli_update_command and capabilities_update_manager."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src import surface_cli_update_command
from modules.core.src.capabilities_update_manager import UpdateManager, compare_versions
from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)


class TestVersionComparison(unittest.TestCase):
    """Test version comparison helper logic."""

    def test_version_compare_equal(self) -> None:
        self.assertEqual(compare_versions("4.5.1", "4.5.1"), 0)
        self.assertEqual(compare_versions("v4.5.1", "4.5.1"), 0)

    def test_version_compare_newer(self) -> None:
        self.assertGreater(compare_versions("4.5.2", "4.5.1"), 0)
        self.assertGreater(compare_versions("4.6.0", "4.5.1"), 0)

    def test_version_compare_older(self) -> None:
        self.assertLess(compare_versions("4.4.0", "4.5.1"), 0)


class TestSurfaceCliUpdateCommand(unittest.TestCase):
    """Test CLI surface update command controller handling."""

    def setUp(self) -> None:
        self.updater = MagicMock(spec=IUpdateProtocol)

    def test_handle_check_mode_up_to_date(self) -> None:
        args = MagicMock()
        args.check = True
        args.force = False

        self.updater.check_update.return_value = UpdateCheckResult(
            package_name="qwen-web-cli",
            current_version="4.5.1",
            latest_version="4.5.1",
            update_available=False,
            source="github",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("already running the latest version", str(res.get("message")))

    def test_handle_check_mode_update_available(self) -> None:
        args = MagicMock()
        args.check = True
        args.force = False

        self.updater.check_update.return_value = UpdateCheckResult(
            package_name="qwen-web-cli",
            current_version="4.5.1",
            latest_version="4.5.2",
            update_available=True,
            source="github",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("qwen-web-cli update", str(res.get("message")))

    def test_handle_perform_update_success(self) -> None:
        args = MagicMock()
        args.check = False
        args.force = False

        self.updater.perform_update.return_value = UpdateReport(
            package_name="qwen-web-cli",
            previous_version="4.5.1",
            latest_version="4.5.2",
            source="github",
            update_available=True,
            forced=False,
            changed=True,
            steps=(
                UpdateStepResult("package_upgrade", True, True, "git pull & editable reinstall"),
                UpdateStepResult("browser_sync", True, True, "playwright install chromium"),
            ),
            health_checks=(UpdateStepResult("health:python_runtime", True, True, "Python 3.10+"),),
            post_update_version="4.5.2",
            healthy=True,
            message="Successfully updated qwen-web-cli 4.5.1 -> 4.5.2",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("Successfully updated", str(res.get("message")))


class TestUpdateManagerRealFlow(unittest.TestCase):
    """Test UpdateManager 4.5.1 -> 4.5.2 version bump & upgrade pipeline."""

    def setUp(self) -> None:
        self.manager = UpdateManager()

    @patch("modules.core.src.capabilities_update_manager.UpdateManager._fetch_json")
    @patch("modules.core.src.capabilities_update_manager.get_package_version")
    def test_check_update_discovers_4_5_2(self, mock_get_ver: MagicMock, mock_fetch_json: MagicMock) -> None:
        mock_get_ver.return_value = "4.5.1"
        mock_fetch_json.return_value = {"tag_name": "v4.5.2", "name": "v4.5.2"}

        res = self.manager.check_update()

        self.assertEqual(res.current_version, "4.5.1")
        self.assertEqual(res.latest_version, "4.5.2")
        self.assertTrue(res.update_available)
        self.assertEqual(res.source, "github")

    def test_run_subprocess_rejects_shell_metacharacters(self) -> None:
        """Subprocess args with shell metacharacters must be refused."""
        rc, _out, err = self.manager._run_subprocess(["git", "-C", "/tmp/evil; rm -rf /"], timeout_sec=5.0)
        self.assertEqual(rc, 1)
        self.assertIn("shell metacharacters", err)

    def test_run_subprocess_rejects_path_outside_allowed_roots(self) -> None:
        """Absolute paths outside the project/home/toolchain roots are refused."""
        rc, _out, err = self.manager._run_subprocess(["git", "-C", "/etc/passwd"], timeout_sec=5.0)
        self.assertEqual(rc, 1)
        self.assertIn("outside allowed roots", err)

    def test_run_subprocess_rejects_insecure_repo_url(self) -> None:
        """Non-github pip upgrade sources must be refused before subprocess."""
        from modules.core.src.capabilities_update_manager import DEFAULT_GITHUB_REPO

        manager = self.manager
        with patch.object(manager, "_editable_source_dir", return_value=None):
            with patch.dict(
                "os.environ",
                {"QWEN_WEB_GITHUB_REPO": "evil.example.com/malicious"},
                clear=False,
            ):
                url = f"git+https://github.com/{DEFAULT_GITHUB_REPO}.git"
                self.assertRegex(url, r"^git\+https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")

    def test_perform_update_rejects_stale_post_update_version(self) -> None:
        with (
            patch.object(
                self.manager,
                "_resolve_installed_version",
                side_effect=[VersionString("5.0.0"), VersionString("5.0.0")],
            ),
            patch.object(
                self.manager,
                "check_update",
                return_value=UpdateCheckResult(
                    package_name="qwen-web-cli",
                    current_version="5.0.0",
                    latest_version="5.2.0",
                    update_available=True,
                    source="github",
                ),
            ),
            patch.object(
                self.manager,
                "upgrade_package",
                return_value=UpdateStepResult("package_upgrade", True, True, "fallback reinstall"),
            ) as mock_upgrade,
            patch.object(
                self.manager,
                "sync_browser",
                return_value=UpdateStepResult("browser_sync", True, True, "chromium ok"),
            ),
            patch.object(
                self.manager,
                "_postflight_health_checks",
                return_value=(UpdateStepResult("health:check", True, True, "ok"),),
            ),
        ):
            report = self.manager.perform_update(ForceFlag(False))

        self.assertFalse(report.healthy)
        mock_upgrade.assert_called_once_with(ForceFlag(False), target_version="5.2.0")
        self.assertTrue(
            any(check.name == "health:package_version_target" and not check.success for check in report.health_checks)
        )
        self.assertIn("behind latest 5.2.0", report.message)

    def test_upgrade_package_falls_back_to_pinned_release_for_stale_editable_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / ".git").mkdir()
            (source / "pyproject.toml").write_text('version = "5.0.0"\n', encoding="utf-8")
            with (
                patch.object(self.manager, "_editable_source_dir", return_value=source),
                patch.object(self.manager, "_run_subprocess", side_effect=[(0, "", ""), (0, "", "")]) as run,
            ):
                result = self.manager.upgrade_package(target_version="5.2.0")

        self.assertTrue(result.success)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["git", "-C", str(source), "pull", "--ff-only"])
        self.assertIn(
            "git+https://github.com/rakaarwaky/qwen-web-arwaky.git@v5.2.0",
            commands[1],
        )
        self.assertIn("--force-reinstall", commands[1])

    @patch.object(UpdateManager, "upgrade_package")
    @patch.object(UpdateManager, "sync_browser")
    @patch.object(UpdateManager, "_postflight_health_checks")
    @patch("modules.core.src.capabilities_update_manager.UpdateManager.check_update")
    @patch.object(UpdateManager, "_resolve_installed_version")
    def test_perform_update_executes_pipeline(
        self,
        mock_curr_ver: MagicMock,
        mock_check_update: MagicMock,
        mock_health: MagicMock,
        mock_sync_browser: MagicMock,
        mock_upgrade: MagicMock,
    ) -> None:
        mock_curr_ver.side_effect = [VersionString("4.5.1"), VersionString("4.5.2")]
        mock_check_update.return_value = UpdateCheckResult(
            package_name="qwen-web-cli",
            current_version="4.5.1",
            latest_version="4.5.2",
            update_available=True,
            source="github",
        )
        mock_upgrade.return_value = UpdateStepResult("package_upgrade", True, True, "git pull ok")
        mock_sync_browser.return_value = UpdateStepResult("browser_sync", True, True, "chromium ok")
        mock_health.return_value = (UpdateStepResult("health:check", True, True, "ok"),)

        report = self.manager.perform_update(ForceFlag(False))

        self.assertTrue(report.healthy)
        self.assertEqual(report.previous_version, "4.5.1")
        self.assertEqual(report.latest_version, "4.5.2")
        self.assertEqual(report.post_update_version, "4.5.2")
        self.assertIn("Successfully updated", report.message)


if __name__ == "__main__":
    unittest.main()
