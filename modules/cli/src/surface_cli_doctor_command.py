"""CLI surface: doctor command — system diagnostic checks (AES406).

Audits environment health: Python version, Playwright Chromium, workspace
initialization, the session pool (the single source of truth for session
state), output writability, host capacity for the browser fan-out, the
effective Chromium sandbox mode, and the environment variable contract.
With ``--smoke``, a final check runs a headless browser round-trip on the
saved session to verify the full pipeline end-to-end (issue #322).

:func:`run_doctor_checks` is the library form; every caller — the CLI
report and the update pipeline's postflight gate — injects a session
aggregate, so doctor and ``session list`` can never disagree about the
pool (issue #294). The failure footer points at the operator runbooks
(issue #299).
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from modules.cli.src.surface_cli_json_hook import status_glyph
from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_MAX_WORKERS,
    DEFAULT_OUTPUT,
    LOCAL_WS_DIR,
    SESSIONS_DIR,
)
from modules.shared.src.common.utility_core_capacity import describe_capacity, recommended_max_workers
from modules.shared.src.common.utility_core_env import (
    ENVIRONMENT,
    SENTRY_DSN,
    effective_config,
    runbook_index,
    unknown_env_vars,
    validate_env,
)
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.taxonomy_session_vo import SessionRequest
from modules.shared.src.update.utility_update_chromium import playwright_browsers_path

RULE = "─" * 50
PRODUCTION_ENV = "production"
RUNBOOK_ROOT = "docs/"


def _env(name: str) -> str:
    """Return a trimmed environment value, or the empty string when unset."""
    return os.environ.get(name, "").strip()


def _flag(name: str) -> bool:
    """Return True when the environment switch is one of the truthy spellings."""
    return _env(name).casefold() in {"1", "true", "yes"}


def _sandbox_unavailable() -> bool:
    """Return True when the host cannot host Chromium's OS sandbox.

    Chromium needs seccomp-bpf or unprivileged user namespaces; a container or a
    hardened host can lack both, and Chromium then refuses to start without
    ``--no-sandbox``. Mirrors the runtime detection in
    ``utility_core_config_factory.sandbox_unavailable`` so the reported mode
    matches the mode the browser actually launches with.
    """
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
    """Return ``sandboxed``, ``sandboxed (forced)``, or ``disabled`` plus the reason.

    The default is the OS sandbox; ``--no-sandbox`` is only ever applied on an
    explicit opt-in or a host that cannot provide one (issue #290).
    """
    if _flag("QWEN_DISABLE_SANDBOX"):
        return "disabled (QWEN_DISABLE_SANDBOX)"
    if _sandbox_unavailable():
        return "disabled (host has no seccomp filter or user namespaces)"
    if _flag("QWEN_ENABLE_SANDBOX"):
        return "sandboxed (forced via QWEN_ENABLE_SANDBOX)"
    return "sandboxed"


def _check(name: str, passed: bool, detail: str, severity: str = "ok") -> dict[str, Any]:
    """Build one diagnostic record.

    Severity vocabulary: ``"ok"`` for a passing check, ``"warning"`` for a
    check that passes with a concern worth surfacing (a host limitation or an
    operator misconfiguration), and ``"error"`` only for ``passed=False`` —
    so a report consumer can tell a hard failure from a soft concern.
    """
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
    """Report whether a Chromium binary is reachable for Playwright to launch.

    A cache hit or a trusted system binary is enough for the common path. The
    expensive ``sync_playwright`` cold-start probe runs only when the deep
    probe is on so the default report stays fast.
    """
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
    """Report session pool status.

    The pool is the single source of truth: an empty pool is reported as
    "no session", so doctor and ``session list`` can never disagree about a
    legacy ``DEFAULT_SESSION`` profile that the pool does not know about.
    """
    pool = session.execute(SessionRequest(verb="list_sessions")).sessions
    entries = list(pool) if pool else []

    if entries:
        lines = [f"Session pool: {len(entries)} account(s) under {SESSIONS_DIR}"]
        for s in entries:
            icon = (
                status_glyph("health_ok")
                if s.is_healthy
                else (
                    status_glyph("health_limited")
                    if s.is_limited
                    else (status_glyph("health_auth") if s.is_auth_required else status_glyph("health_unknown"))
                )
            )
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
    """Report the browser fan-out this host can carry and the source of the limit.

    The limit is derived from available memory rather than a fixed constant, so
    the reported number matches what the job executor will actually use
    (issue #291). The severity vocabulary: ``"ok"`` for the derived limit or a
    deliberate under-configuration, ``"warning"`` only for an override that
    exceeds the derived limit — memory oversubscription, the dangerous case,
    must not read as healthy.
    """
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
    """Report registry validation failures and unrecognized ``QWEN_``/``QWA_`` names.

    A typo'd switch silently selects a different runtime mode, so an unknown name
    is surfaced as a warning naming the registered alternatives (issue #292).
    """
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
    """Warn when a production host has no external error tracking configured.

    Both Sentry and OTLP left unset means failures reach only the rotating file
    log, so a production deployment fails silently (issue #297).
    """
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
    """Run a headless browser round-trip against the saved session.

    Delegates to ``ISessionAggregate.execute()`` so the surface reuses
    the Core launch → navigate → textarea-check → close pipeline with no new
    capability code. Every caller injects the aggregate; a missing one is
    a wiring gap, reported as such rather than as a synthetic failure.
    """
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
    """Run every diagnostic check and return the records as plain dictionaries.

    The library form of ``doctor``: the CLI ``build_smoke_gate`` calls the
    same function, so the interactive report and the CLI smoke gate cannot
    disagree (issue #294). Root injects the Capabilities health probe
    (``capabilities_config_health_probe``) as the update pipeline's gate,
    and that probe runs the same non-interactive checks at gate-execution
    time. The session aggregate is required: the pool is doctor's single
    source of truth for session state.
    """
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
    depends only on an injected callable, never on a Surface. The checks run
    at gate-execution time (not container-construction time) so the post-update
    gate reflects the post-upgrade state (issue #506).

    Pass the aggregate, e.g. ``session_manager.load_pool()`` or a production
    ``ISessionAggregate`` — there is no default, so a wiring gap cannot
    masquerade as an empty pool.
    """
    aggregate = session

    def _gate() -> tuple[tuple[str, bool, str], ...]:
        checks = run_doctor_checks(session=aggregate)
        return tuple((str(check["name"]), bool(check["passed"]), str(check["detail"])) for check in checks)

    return _gate


def summarize(checks: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """Split checks into the all-passed flag plus the failed and warning lists."""
    failed = [c for c in checks if not c["passed"]]
    warned = [c for c in checks if c["passed"] and c.get("severity") == "warning"]
    return not failed, failed, warned


def run_doctor(
    session: ISessionAggregate,
    json_output: bool = False,
    smoke: bool = False,
    deep: bool = False,
) -> int:
    """Perform system health diagnostics and print a formatted report or JSON summary.

    With *smoke* enabled, a final check runs a headless browser session round-trip
    through the injected session aggregate; it needs a saved session and Chromium.
    ``--deep`` (or the ``QWEN_DOCTOR_DEEP`` alias) runs the heavy Playwright
    probe; *deep* and the flag are OR-ed, the env var is only an alias.
    """
    include_heavy = deep or _flag("QWEN_DOCTOR_DEEP")
    checks = run_doctor_checks(
        include_heavy=include_heavy,
        smoke=smoke,
        session=session,
    )
    all_passed, failed, warned = summarize(checks)

    if json_output:
        print(
            json.dumps(
                {
                    "status": "healthy" if all_passed else "unhealthy",
                    "checks": checks,
                    "environment": effective_config(),
                    "capacity": {
                        "recommended_max_workers": recommended_max_workers(),
                        "max_workers_cap": DEFAULT_MAX_WORKERS,
                    },
                    "runbooks": runbook_index(),
                },
                indent=2,
            )
        )
        return 0 if all_passed else 1

    print("\n🔍 Qwen Web Automation System Health Diagnostic\n" + RULE)
    for check in checks:
        if not check["passed"]:
            icon = status_glyph("fail")
        elif check.get("severity") == "warning":
            icon = status_glyph("warn")
        else:
            icon = status_glyph("ok")
        print(f"  {icon} {check['name']}")
        print(f"      {check['detail']}")

    print(RULE)
    if failed:
        print(f"{status_glyph('warn')} {len(failed)} check(s) failed; fix items marked {status_glyph('fail')} above.")
        print(f"   Operator runbooks: {RUNBOOK_ROOT} (keyed by ErrorCategory)\n")
        return 1
    if warned:
        print(f"{status_glyph('warn')} All checks passed with {len(warned)} warning(s); runbooks at {RUNBOOK_ROOT}")
        print(f"   Operator runbooks: {RUNBOOK_ROOT} (keyed by ErrorCategory)\n")
        return 0
    print(f"{status_glyph('ok')} All diagnostic checks passed! System is healthy and ready for execution.\n")
    return 0


__all__ = [
    "PRODUCTION_ENV",
    "build_smoke_gate",
    "run_doctor",
    "run_doctor_checks",
    "summarize",
]
