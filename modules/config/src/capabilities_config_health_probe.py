"""Capabilities: environment health probe (AES403).

Implements the ``ISmokeGate`` callable signature the update pipeline depends
on (see ``contract_update_protocol``): after an upgrade the pipeline re-runs
the operator diagnostics and rolls back when they fail (issue #294).

Before this seam the gate was built in the CLI Surface, which made the Root
composition layer import a Surface module and made the update pipeline
transitively depend on presentation. The checks themselves live here in the
Capabilities layer; the CLI ``doctor`` command and the Root container both
consume this same probe, so the interactive report and the postflight gate
can never disagree (issue #294).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_OUTPUT,
    LOCAL_WS_DIR,
    SESSIONS_DIR,
)
from modules.shared.src.common.utility_core_capacity import describe_capacity, recommended_max_workers
from modules.shared.src.common.utility_core_env import (
    ENVIRONMENT,
    SENTRY_DSN,
    effective_config,
    unknown_env_vars,
    validate_env,
)
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.taxonomy_session_vo import SessionRequest
from modules.shared.src.update.utility_update_chromium import playwright_browsers_path

PRODUCTION_ENV = "production"
RUNBOOK_ROOT = "docs/"

RULE = "─" * 50


def _env(name: str) -> str:
    """Return a trimmed environment value, or the empty string when unset."""
    return os.environ.get(name, "").strip()


def _flag(name: str) -> bool:
    """Return True when the environment switch is one of the truthy spellings."""
    return _env(name).casefold() in {"1", "true", "yes"}


def _sandbox_unavailable() -> bool:
    """Return True when the host cannot host Chromium's OS sandbox."""
    if sys.platform != "linux":
        return False
    try:
        status = Path("/proc/self/status").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    seccomp = next(
        (
            int(line.split()[1])
            for line in status.splitlines()
            if line.startswith("Seccomp:") and line.split()[1].isdigit()
        ),
        0,
    )
    if seccomp == 0:
        return True
    return any(
        sysctl.exists() and sysctl.read_text(encoding="utf-8").strip() == "0"
        for sysctl in (
            Path("/proc/sys/kernel/unprivileged_userns_clone"),
            Path("/proc/sys/user/max_user_namespaces"),
        )
    )


def _sandbox_mode() -> str:
    """Return ``sandboxed``, ``sandboxed (forced)``, or ``disabled`` plus the reason."""
    if _flag("QWEN_DISABLE_SANDBOX"):
        return "disabled (QWEN_DISABLE_SANDBOX)"
    if _sandbox_unavailable():
        return "disabled (host has no seccomp filter or user namespaces)"
    if _flag("QWEN_ENABLE_SANDBOX"):
        return "sandboxed (forced via QWEN_ENABLE_SANDBOX)"
    return "sandboxed"


def _check(name: str, passed: bool, detail: str, severity: str = "ok") -> dict[str, Any]:
    """Build one diagnostic record."""
    return {"name": name, "passed": passed, "detail": detail, "severity": severity}


def _check_python() -> dict[str, Any]:
    """Report the interpreter version against the supported floor."""
    ok = sys.version_info >= (3, 10)
    return _check(
        "Python Version",
        ok,
        f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (>= 3.10)",
    )


def _check_chromium(include_heavy: bool) -> dict[str, Any]:
    """Report whether a Chromium binary is reachable for Playwright to launch."""
    from modules.shared.src.update.utility_update_browser_binary import find_chrome_binary

    trusted_binary = find_chrome_binary()
    browsers_dir = playwright_browsers_path()
    executable: str | None = None
    if trusted_binary or (browsers_dir.exists() and any(browsers_dir.glob("chromium-*"))):
        detail = "Chromium binary found in Playwright cache or system PATH"
        if _flag("QWEN_DOCTOR_SHOW_PATH"):
            detail = f"{detail}; cache {browsers_dir}"
            if trusted_binary:
                detail = f"{detail}; trusted binary {trusted_binary}"
        return _check("Playwright Chromium Browser", True, detail)
    if not include_heavy:
        return _check(
            "Playwright Chromium Browser",
            False,
            "Chromium binary not found in cache or PATH (run with --deep for a full probe)",
        )
    print("Running a deep Playwright probe (cold start); this can take a while...", file=sys.stderr)
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        try:
            executable = playwright.chromium.executable_path
            found = bool(executable) and Path(executable).exists()
        finally:
            playwright.stop()
    except Exception as exc:
        return _check(
            "Playwright Chromium Browser",
            False,
            f"Chromium binary missing (run: python3 -m playwright install chromium): {exc}",
        )
    return _check(
        "Playwright Chromium Browser",
        found,
        f"Chromium binary at: {executable}"
        if found
        else "Chromium binary missing (run: python3 -m playwright install chromium)",
    )


def _check_workspace() -> dict[str, Any]:
    """Report whether ``qwa init`` created the per-directory XDG symlinks."""
    dot_qwen = Path.cwd() / LOCAL_WS_DIR
    ok = dot_qwen.exists() and any((dot_qwen / link).exists() for link in ("log", "output"))
    return _check(
        "Workspace Initialization",
        ok,
        f"Workspace found at {dot_qwen} (per-directory; session/output are global XDG)"
        if ok
        else "Workspace not initialized in this directory (run: qwen-web-arwaky init). "
        "Note: workspaces are per-directory; your login session and outputs are global.",
    )


def _check_session(session: ISessionAggregate) -> dict[str, Any]:
    """Report session pool status."""
    pool = session.execute(SessionRequest(verb="list_sessions")).sessions
    entries = list(pool) if pool else []

    if entries:
        lines = [f"Session pool: {len(entries)} account(s) under {SESSIONS_DIR}"]
        for s in entries:
            icon = "✅" if s.is_healthy else ("🟡" if s.is_limited else ("🔑" if s.is_auth_required else "🔶"))
            lines.append(f"  {icon} {s.session_id} ({s.name}): {s.status.value}")
        healthy = sum(1 for s in entries if s.is_healthy)
        limited = sum(1 for s in entries if s.is_limited)
        detail = f"{healthy} healthy, {limited} limited"
        severity = "warning" if healthy == 0 else "ok"
        return _check("Session Authentication Token", healthy > 0, detail, severity=severity)

    return _check(
        "Session Authentication Token",
        False,
        f"No session in the pool under {SESSIONS_DIR} (run: qwen-web-arwaky session login --name default)",
    )


def _check_output_writable() -> dict[str, Any]:
    """Report whether the XDG output directory accepts writes."""
    try:
        DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
        probe = DEFAULT_OUTPUT / ".doctor_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return _check(
            "Output Storage Permission",
            False,
            f"Output directory not writable ({DEFAULT_OUTPUT}): {exc} (runbook: docs/disk-exhaustion.md)",
        )
    return _check("Output Storage Permission", True, f"Output directory writable ({DEFAULT_OUTPUT})")


def _check_capacity() -> dict[str, Any]:
    """Report the browser fan-out this host can carry and the source of the limit."""
    configured = _env("QWEN_WEB_MAX_WORKERS")
    derived = recommended_max_workers()
    detail = describe_capacity()
    if configured.isdigit():
        oversubscribed = int(configured) > derived
        return _check(
            "Host Capacity",
            True,
            f"{detail}; QWEN_WEB_MAX_WORKERS={configured} overrides the derived limit",
            severity="warning" if oversubscribed else "ok",
        )
    return _check("Host Capacity", True, detail)


def _check_sandbox() -> dict[str, Any]:
    """Report the effective Chromium sandbox mode and what drove it."""
    mode = _sandbox_mode()
    disabled = mode.startswith("disabled")
    detail = f"Chromium sandbox mode: {mode}"
    if disabled and _sandbox_unavailable() and not _flag("QWEN_ENABLE_SANDBOX"):
        detail += " — expected on this host; re-enable by granting seccomp or user namespaces"
        severity = "warning"
    elif disabled:
        detail += " — every non-login job runs without Chromium's process sandbox"
        severity = "warning"
    else:
        severity = "ok"
    return _check("Chromium Sandbox", True, detail, severity=severity)


def _check_env_contract() -> list[dict[str, Any]]:
    """Report registry validation failures and unrecognized ``QWEN_``/``QWA_`` names."""
    checks: list[dict[str, Any]] = []
    problems = validate_env()
    checks.append(
        _check(
            "Environment Contract",
            not problems,
            "all recognized variables parse cleanly" if not problems else "; ".join(problems) + " (see .env.example)",
        )
    )
    unknown = unknown_env_vars()
    if unknown:
        checks.append(
            _check(
                "Unrecognized Environment Variables",
                True,
                f"set but not in the registry: {', '.join(unknown)} — a typo changes runtime behaviour silently; "
                f"known names: {', '.join(sorted(effective_config()))}",
                severity="warning",
            )
        )
    return checks


def _check_observability() -> dict[str, Any]:
    """Warn when a production host has no external error tracking configured."""
    sentry = bool(_env(SENTRY_DSN))
    otlp = bool(_env("OTEL_EXPORTER_OTLP_ENDPOINT"))
    if _env(ENVIRONMENT).casefold() == PRODUCTION_ENV and not (sentry or otlp):
        return _check(
            "Observability Backends",
            True,
            "ENVIRONMENT=production with SENTRY_DSN and OTEL_EXPORTER_OTLP_ENDPOINT both unset — "
            "errors reach the local file log only (runbook: docs/other.md)",
            severity="warning",
        )
    mode = "Sentry + OTLP" if sentry and otlp else ("Sentry" if sentry else ("OTLP" if otlp else "file log only"))
    return _check("Observability Backends", True, f"error tracking: {mode}")


def _smoke_check(session: ISessionAggregate | None) -> tuple[bool, str]:
    """Run a headless browser round-trip against the saved session."""
    if session is None:
        return False, "No session aggregate is available; the smoke gate is not wired for this run."
    try:
        from modules.shared.src.session.taxonomy_session_vo import SessionRequest

        response = session.execute(SessionRequest(verb="validate"))
        return response.valid, response.message or "Session validation returned no detail."
    except Exception as exc:
        return False, f"Smoke test failed: {exc}"


def run_doctor_checks(
    *,
    include_heavy: bool = False,
    smoke: bool = False,
    session: ISessionAggregate,
) -> list[dict[str, Any]]:
    """Run every diagnostic check and return the records as plain dictionaries."""
    checks: list[dict[str, Any]] = [
        _check_python(),
        _check_chromium(include_heavy),
        _check_workspace(),
        _check_session(session),
        _check_output_writable(),
        _check_capacity(),
        _check_sandbox(),
    ]
    checks.extend(_check_env_contract())
    checks.append(_check_observability())
    if smoke:
        smoke_ok, smoke_detail = _smoke_check(session)
        checks.append(_check("Browser Smoke Test", smoke_ok, smoke_detail))
    return checks


def build_smoke_gate(
    session: ISessionAggregate,
) -> Callable[[], tuple[tuple[str, bool, str], ...]]:
    """Return a callable the update pipeline runs as its postflight functional gate.

    Returns the non-interactive diagnostic checks as ``(name, passed, detail)``
    triples. The Root layer composes this so the Capabilities update pipeline
    depends only on an injected callable, never on a Surface.
    """
    aggregate = session

    def _gate() -> tuple[tuple[str, bool, str], ...]:
        checks = run_doctor_checks(session=aggregate)
        return tuple((str(check["name"]), bool(check["passed"]), str(check["detail"])) for check in checks)

    return _gate


__all__ = [
    "PRODUCTION_ENV",
    "build_smoke_gate",
    "run_doctor_checks",
]
