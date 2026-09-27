"""Unit tests for surface_cli_update_command and capabilities_update_manager."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src import surface_cli_update_command
from modules.shared.src.contract_core_protocol import IUpdateProtocol
from modules.shared.src.taxonomy_core_vo import (
    ForceFlag,
    UpdateCheckResult,
    UpdateReport,
    UpdateStepResult,
    VersionString,
)
from modules.update.src.capabilities_update_manager import UpdateManager, compare_versions


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
            package_name="qwen-web-arwaky",
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
            package_name="qwen-web-arwaky",
            current_version="4.5.1",
            latest_version="4.5.2",
            update_available=True,
            source="github",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("qwen-web-arwaky update", str(res.get("message")))

    def test_handle_perform_update_success(self) -> None:
        args = MagicMock()
        args.check = False
        args.force = False

        self.updater.perform_update.return_value = UpdateReport(
            package_name="qwen-web-arwaky",
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
            message="Successfully updated qwen-web-arwaky 4.5.1 -> 4.5.2",
        )

        res = surface_cli_update_command.handle(args, self.updater)
        self.assertTrue(res.get("success"))
        self.assertIn("Successfully updated", str(res.get("message")))


class TestUpdateManagerRealFlow(unittest.TestCase):
    """Test UpdateManager 4.5.1 -> 4.5.2 version bump & upgrade pipeline."""

    def setUp(self) -> None:
        self.manager = UpdateManager()

    @patch("modules.update.src.capabilities_update_manager.UpdateManager._fetch_json")
    @patch("modules.update.src.capabilities_update_manager.get_package_version")
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
        from modules.update.src.capabilities_update_manager import DEFAULT_GITHUB_REPO

        manager = self.manager
        with patch.object(manager, "_editable_source_dir", return_value=None):
            with patch.dict(
                "os.environ",
                {"QWEN_WEB_GITHUB_REPO": "evil.example.com/malicious"},
                clear=False,
            ):
                url = f"git+https://github.com/{DEFAULT_GITHUB_REPO}.git"
                self.assertRegex(url, r"^git\+https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")

    def test_fetch_json_rejects_non_github_schemes_and_hosts(self) -> None:
        """Release discovery must never open file, custom, or foreign URLs."""
        self.assertIsNone(self.manager._fetch_json("file:///tmp/release.json"))
        self.assertIsNone(self.manager._fetch_json("https://example.com/releases/latest"))
        self.assertIsNone(self.manager._fetch_json("custom://api.github.com/releases/latest"))

    @patch.dict("os.environ", {"QWEN_WEB_GITHUB_REPO": "evil.example/owner/repo"})
    def test_invalid_repository_input_is_rejected(self) -> None:
        """Repository environment input must remain owner/repository shaped."""
        with self.assertRaises(ValueError):
            self.manager._github_repo_url("6.3.0")

    @patch.object(UpdateManager, "sync_browser")
    @patch.object(UpdateManager, "upgrade_package")
    @patch.object(UpdateManager, "check_update")
    @patch.object(UpdateManager, "current_version")
    def test_perform_update_refuses_unknown_target_without_mutation(
        self,
        mock_current_version: MagicMock,
        mock_check_update: MagicMock,
        mock_upgrade: MagicMock,
        mock_sync_browser: MagicMock,
    ) -> None:
        """An unavailable release target must not run package or browser changes."""
        mock_current_version.return_value = VersionString("6.2.0")
        mock_check_update.return_value = UpdateCheckResult(
            package_name="qwen-web-arwaky",
            current_version="6.2.0",
            latest_version=None,
            update_available=False,
            source="unavailable",
            error="network unavailable",
        )

        report = self.manager.perform_update(ForceFlag(False))

        self.assertFalse(report.healthy)
        self.assertFalse(report.changed)
        self.assertIn("cannot verify target version", report.message)
        mock_upgrade.assert_not_called()
        mock_sync_browser.assert_not_called()

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
                    package_name="qwen-web-arwaky",
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
        pinned_sha = "b8e79ccc4e26ceed72b7b5713d1c64ef3c1a2d68"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / ".git").mkdir()
            (source / "pyproject.toml").write_text('version = "5.0.0"\n', encoding="utf-8")
            with (
                patch.object(self.manager, "_editable_source_dir", return_value=source),
                patch.object(self.manager, "_resolve_release_commit", return_value=("v5.2.0", pinned_sha)),
                patch.object(self.manager, "_run_subprocess", side_effect=[(0, "", ""), (0, "", "")]) as run,
            ):
                result = self.manager.upgrade_package(target_version="5.2.0")

        self.assertTrue(result.success)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["git", "-C", str(source), "pull", "--ff-only"])
        # Issue #368: the fallback installs the immutable commit SHA (never a
        # mutable tag), so a re-pointed release tag cannot swap the code.
        self.assertIn(
            f"git+https://github.com/rakaarwaky/qwen-web-arwaky.git@{pinned_sha}",
            commands[1],
        )
        self.assertNotIn(
            "git+https://github.com/rakaarwaky/qwen-web-arwaky.git@v5.2.0",
            commands[1],
        )
        self.assertIn("--force-reinstall", commands[1])

    @patch.object(UpdateManager, "upgrade_package")
    @patch.object(UpdateManager, "sync_browser")
    @patch.object(UpdateManager, "_postflight_health_checks")
    @patch("modules.update.src.capabilities_update_manager.UpdateManager.check_update")
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
            package_name="qwen-web-arwaky",
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


class TestUpdateManagerShaPinning(unittest.TestCase):
    """Issue #368: installs must pin the release to its immutable commit SHA."""

    SHA_COMMIT = "a" * 40
    SHA_TAG_OBJ = "b" * 40
    SHA_DEREF = "c" * 40

    def setUp(self) -> None:
        self.manager = UpdateManager()

    @patch.object(UpdateManager, "_fetch_json")
    def test_lightweight_tag_resolves_to_commit(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {"ref": "refs/tags/v6.4.0", "object": {"sha": self.SHA_COMMIT, "type": "commit"}}
        url = self.manager._github_pinned_url("6.4.0")
        self.assertEqual(
            url,
            f"git+https://github.com/rakaarwaky/qwen-web-arwaky.git@{self.SHA_COMMIT}",
        )

    @patch.object(UpdateManager, "_fetch_json")
    def test_annotated_tag_is_dereferenced_to_commit(self, mock_fetch: MagicMock) -> None:
        def side_effect(url: str) -> dict:
            if "/git/refs/tags/" in url:
                return {"object": {"sha": self.SHA_TAG_OBJ, "type": "tag"}}
            return {"object": {"sha": self.SHA_DEREF, "type": "commit"}}

        mock_fetch.side_effect = side_effect
        url = self.manager._github_pinned_url("6.4.0")
        self.assertTrue(url.endswith(f"@{self.SHA_DEREF}"))

    @patch.object(UpdateManager, "_fetch_json")
    def test_unresolvable_tag_returns_none(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = None
        self.assertIsNone(self.manager._github_pinned_url("9.9.9"))

    @patch.object(UpdateManager, "_fetch_json")
    def test_malformed_sha_is_refused(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {"object": {"sha": "not-a-real-sha", "type": "commit"}}
        self.assertIsNone(self.manager._github_pinned_url("6.4.0"))

    def test_no_target_version_returns_none(self) -> None:
        self.assertIsNone(self.manager._github_pinned_url(None))

    @patch.object(UpdateManager, "_resolve_release_commit", return_value=None)
    @patch.object(UpdateManager, "_run_subprocess")
    def test_upgrade_refuses_unpinnable_release_fail_closed(self, mock_run: MagicMock, mock_resolve: MagicMock) -> None:
        with patch.object(self.manager, "_editable_source_dir", return_value=None):
            step = self.manager.upgrade_package(target_version="6.4.0")
        self.assertFalse(step.success)
        self.assertFalse(step.executed)
        self.assertIn("refusing to install unverified remote code", step.detail)
        mock_run.assert_not_called()

    @patch.object(UpdateManager, "_fetch_json")
    @patch.object(UpdateManager, "_run_subprocess")
    def test_upgrade_installs_pinned_commit_url(self, mock_run: MagicMock, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {"object": {"sha": self.SHA_COMMIT, "type": "commit"}}
        mock_run.return_value = (0, "ok", "")
        with patch.object(self.manager, "_editable_source_dir", return_value=None):
            step = self.manager.upgrade_package(target_version="6.4.0")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[-1], f"git+https://github.com/rakaarwaky/qwen-web-arwaky.git@{self.SHA_COMMIT}")
        self.assertNotIn("@v6.4.0", cmd[-1])
        self.assertTrue(step.success)

    @patch.object(UpdateManager, "_resolve_release_commit", return_value=None)
    @patch.object(UpdateManager, "_run_subprocess")
    def test_rollback_refuses_unpinnable_release(self, mock_run: MagicMock, mock_resolve: MagicMock) -> None:
        with patch.object(self.manager, "_editable_source_dir", return_value=None):
            steps = self.manager.rollback_to("6.3.0")
        self.assertFalse(steps[0].success)
        self.assertIn("refusing to install unverified remote code", steps[0].detail)
        mock_run.assert_not_called()
