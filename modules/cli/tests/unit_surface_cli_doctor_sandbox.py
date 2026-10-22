"""Branch tests for the doctor sandbox detection and the deep probe.

``_sandbox_unavailable`` / ``_sandbox_mode`` are branch-covered with
monkeypatched ``/proc`` reads and ``sys.platform``: non-Linux short-circuit,
``Seccomp: 0``, userns disabled, malformed ``/proc``, and the env-flag
precedence matrix. The ``--deep`` flag and the ``QWEN_DOCTOR_DEEP`` alias
are pinned against ``run_doctor``'s heavy-probe decision.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from modules.cli.src.surface_cli_doctor_command import (
    _check_chromium,
    _flag,
    _sandbox_mode,
    _sandbox_unavailable,
)


def _proc_status(seccomp: str = "2") -> str:
    return f"Name:\tpython\nSeccomp:\t{seccomp}\nSeccomp_filters:\t1\n"


class _FakePath:
    """Path-like stand-in used to monkeypatch ``Path`` reads in the module."""

    def __init__(self, target: Path | _FakePath | str, *, exists: bool = True, text: str = "") -> None:
        self._target = target
        self._exists = exists
        self._text = text

    def exists(self) -> bool:
        return self._exists

    def read_text(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        if not self._exists:
            raise OSError("unreadable")
        return self._text


def _patch_proc(monkeypatch, status_text: str) -> None:
    """Point the doctor's ``/proc`` reads at a fixed status document."""
    fake = _FakePath(Path("/proc/self/status"), exists=True, text=status_text)
    monkeypatch.setattr(
        "modules.cli.src.surface_cli_doctor_command.Path",
        lambda *args, **kwargs: fake,
    )


def _patch_sysctls(monkeypatch, *, seccomp: str = "2", userns: str, max_user: str) -> None:
    originals: dict[Path, str] = {
        Path("/proc/self/status"): _proc_status(seccomp),
        Path("/proc/sys/kernel/unprivileged_userns_clone"): userns,
        Path("/proc/sys/user/max_user_namespaces"): max_user,
    }

    class _SysctlPath:
        """Path stand-in: status + userns sysctls exist with fixed text."""

        def __init__(self, target: str | Path) -> None:
            self._target = Path(target)

        def exists(self) -> bool:
            return self._target in originals

        def read_text(self, encoding: str = "utf-8", errors: str | None = None) -> str:
            if self._target not in originals:
                raise OSError("missing path")
            return originals[self._target]

    monkeypatch.setattr("modules.cli.src.surface_cli_doctor_command.Path", _SysctlPath)


# ─── non-Linux short-circuit ────────────────────────────────────────────────


def test_non_linux_never_reports_an_unavailable_sandbox(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _sandbox_unavailable() is False


def test_non_linux_reports_the_os_sandbox(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)
    monkeypatch.delenv("QWEN_ENABLE_SANDBOX", raising=False)
    assert _sandbox_mode() == "sandboxed"


# ─── Linux /proc branches ──────────────────────────────────────────────────


def test_seccomp_zero_means_the_host_cannot_sandbox(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    _patch_proc(monkeypatch, _proc_status("0"))
    assert _sandbox_unavailable() is True


def test_seccomp_filter_keeps_the_sandbox(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    _patch_proc(monkeypatch, _proc_status("2"))
    _patch_sysctls(monkeypatch, userns="1", max_user="100")
    assert _sandbox_unavailable() is False


def test_userns_disabled_means_the_host_cannot_sandbox(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    _patch_proc(monkeypatch, _proc_status("2"))
    _patch_sysctls(monkeypatch, userns="0", max_user="100")
    assert _sandbox_unavailable() is True


def test_max_user_namespaces_zero_means_the_host_cannot_sandbox(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    _patch_proc(monkeypatch, _proc_status("2"))
    _patch_sysctls(monkeypatch, userns="1", max_user="0")
    assert _sandbox_unavailable() is True


def test_malformed_proc_is_treated_as_sandboxable(monkeypatch) -> None:
    """A /proc document without a parseable Seccomp line is treated as no filter."""
    monkeypatch.setattr(sys, "platform", "linux")
    _patch_proc(monkeypatch, "Name:\tpython\nSomeOtherField:\tgarbage\n")
    assert _sandbox_unavailable() is True


# ─── env-flag precedence matrix ─────────────────────────────────────────────


def test_sandbox_mode_precedence_matrix(monkeypatch) -> None:
    """QWEN_DISABLE_SANDBOX > host detection > QWEN_ENABLE_SANDBOX > default."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        "modules.cli.src.surface_cli_doctor_command._sandbox_unavailable",
        lambda: False,
    )

    monkeypatch.delenv("QWEN_DISABLE_SANDBOX", raising=False)
    monkeypatch.delenv("QWEN_ENABLE_SANDBOX", raising=False)
    assert _sandbox_mode() == "sandboxed"

    monkeypatch.setenv("QWEN_ENABLE_SANDBOX", "1")
    assert _sandbox_mode() == "sandboxed (forced via QWEN_ENABLE_SANDBOX)"

    monkeypatch.setenv("QWEN_DISABLE_SANDBOX", "1")
    assert _sandbox_mode() == "disabled (QWEN_DISABLE_SANDBOX)"
    monkeypatch.delenv("QWEN_DISABLE_SANDBOX")

    monkeypatch.setattr(
        "modules.cli.src.surface_cli_doctor_command._sandbox_unavailable",
        lambda: True,
    )
    assert _sandbox_mode() == "disabled (host has no seccomp filter or user namespaces)"


def test_flag_accepts_the_truthy_spellings(monkeypatch) -> None:
    for spelling in ("1", "true", "YES", "True"):
        monkeypatch.setenv("QWEN_DOCTOR_DEEP", spelling)
        assert _flag("QWEN_DOCTOR_DEEP") is True
    for spelling in ("0", "false", "no", ""):
        monkeypatch.setenv("QWEN_DOCTOR_DEEP", spelling)
        assert _flag("QWEN_DOCTOR_DEEP") is False


# ─── deep probe: --deep flag and the QWEN_DOCTOR_DEEP alias ────────────────


def test_deep_probe_notice_before_the_playwright_probe(capsys, monkeypatch) -> None:
    """The heavy probe is preceded by a stderr notice so the wait is explained."""

    monkeypatch.setattr(
        "modules.shared.src.update.utility_update_browser_binary.find_chrome_binary",
        lambda: None,
    )
    monkeypatch.setattr(
        "modules.cli.src.surface_cli_doctor_command.playwright_browsers_path",
        lambda: Path("/nonexistent-playwright-cache"),
    )

    with patch("playwright.sync_api.sync_playwright") as playwright_api:
        instance = playwright_api.return_value.start.return_value
        instance.chromium.executable_path = "/tmp/chromium"
        with patch("pathlib.Path.exists", return_value=True):
            record = _check_chromium(include_heavy=True)
    assert record["passed"] is True
    assert "Running a deep Playwright probe" in capsys.readouterr().err


def test_light_probe_emits_no_stderr_notice(capsys, monkeypatch) -> None:
    """The light path leaves stderr clean so headless logs stay quiet."""

    monkeypatch.setattr(
        "modules.shared.src.update.utility_update_browser_binary.find_chrome_binary",
        lambda: Path("/usr/bin/chromium"),
    )
    _check_chromium(include_heavy=False)
    assert capsys.readouterr().err == ""


def test_deep_flag_runs_the_heavy_probe(monkeypatch) -> None:
    """run_doctor(deep=True) drives include_heavy without the env alias."""
    called: dict[str, bool] = {}

    def _spy_checks(*, include_heavy: bool = False, smoke: bool = False, session=None) -> list[dict]:
        called["heavy"] = include_heavy
        return []

    monkeypatch.setattr("modules.cli.src.surface_cli_doctor_command.run_doctor_checks", _spy_checks)
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    monkeypatch.delenv("QWEN_DOCTOR_DEEP", raising=False)
    run_doctor(json_output=False, deep=True, session=_pool_aggregate())
    assert called["heavy"] is True


def test_deep_env_alias_drives_the_heavy_probe(monkeypatch) -> None:
    called: dict[str, bool] = {}

    def _spy_checks(*, include_heavy: bool = False, smoke: bool = False, session=None) -> list[dict]:
        called["heavy"] = include_heavy
        return []

    monkeypatch.setattr("modules.cli.src.surface_cli_doctor_command.run_doctor_checks", _spy_checks)
    from modules.cli.src.surface_cli_doctor_command import run_doctor

    monkeypatch.setenv("QWEN_DOCTOR_DEEP", "1")
    run_doctor(json_output=False, deep=False, session=_pool_aggregate())
    assert called["heavy"] is True


def test_smoke_gate_runs_with_an_injected_aggregate() -> None:
    """The config health-probe gate yields name/passed/detail triples from the pool."""
    from modules.cli.src.surface_cli_doctor_command import run_doctor_checks
    from modules.config.src.capabilities_config_health_probe import ConfigHealthProbe

    gate = ConfigHealthProbe().build_gate(_pool_aggregate(), run_doctor_checks)
    results = gate()
    assert results
    for name, passed, detail in results:
        assert isinstance(name, str)
        assert isinstance(passed, bool)
        assert isinstance(detail, str)
    assert "Browser Smoke Test" not in {name for name, _, _ in results}


def test_doctor_and_gate_require_an_aggregate() -> None:
    """run_doctor and the health-probe gate require a session aggregate — no default, no raise site."""
    import pytest

    from modules.cli.src.surface_cli_doctor_command import run_doctor, run_doctor_checks
    from modules.config.src.capabilities_config_health_probe import ConfigHealthProbe

    with pytest.raises(TypeError, match="required positional argument: 'session'"):
        run_doctor(json_output=False)  # type: ignore[call-arg]  # deliberately omitting required session arg
    with pytest.raises(TypeError, match="session"):
        ConfigHealthProbe().build_gate(run_checks=run_doctor_checks)  # type: ignore[call-arg]  # deliberately omitting required session arg


def _pool_aggregate():
    """Test-side aggregate answering every verb from an empty pool."""
    from unittest.mock import MagicMock

    from modules.shared.src.session.taxonomy_session_vo import SessionList, SessionResponse

    aggregate = MagicMock()
    aggregate.execute.return_value = SessionResponse(sessions=SessionList([]), message="0 sessions")
    return aggregate
