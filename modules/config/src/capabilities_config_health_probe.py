"""Capabilities: config health probe (AES403).

Implements ``IConfigHealthProbeProtocol`` so the doctor diagnostic checks
are owned by the Capabilities layer and injected through a seam instead of
imported from the CLI Surface (issue #506 / #294).

The callable signature wired into the update pipeline is ``ISmokeGate`` —
``Callable[[], tuple[tuple[str, bool, str], ...]]`` — produced by
``build_smoke_gate(session)``.  At gate-execution time the probe re-runs
every check so the post-update gate reflects the post-upgrade state.

Root composes a ``ConfigHealthProbe`` instance with a live
``ISessionAggregate`` at container-construction time; the update
pipeline's ``UpdateVerifyCapability`` receives the resulting callable
through dependency injection and never reaches for the CLI layer.
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
from modules.shared.src.common.utility_core_capacity import recommended_max_workers
from modules.shared.src.common.utility_core_env import (
    ENVIRONMENT,
    SENTRY_DSN,
    effective_config,
    unknown_env_vars,
    validate_env,
)
from modules.shared.src.config.contract_config_protocol import IConfigHealthProbeProtocol
from modules.shared.src.config.taxonomy_config_vo import HealthProbeRecord, HealthProbeRecords
from modules.shared.src.session.contract_session_aggregate import ISessionAggregate
from modules.shared.src.session.taxonomy_session_vo import SessionRequest
from modules.shared.src.update.utility_update_chromium import playwright_browsers_path

# Block 1: Class Definition & Constructor


class ConfigHealthProbe(IConfigHealthProbeProtocol):
    """Host health probe capability (AES403).

    Owns every diagnostic check that the CLI ``doctor`` command runs and the
    update pipeline's postflight smoke gate exercises, so no caller has to
    reach into the Surface to run the same checks twice.
    """

    # Block 2: Protocol Method Implementation

    def probe(self, session: ISessionAggregate | None = None) -> HealthProbeRecords:
        """Run every diagnostic check and return the records as plain dicts.

        When *session* is supplied the "Session Authentication Token" check
        queries the pool (the single source of truth for session state); when
        it is absent the check still records an empty-pool result so the
        probe never raises on a missing aggregate.
        """
        checks: list[dict[str, Any]] = [
            _check_python(),
            _check_chromium(),
            _check_workspace(),
        ]
        if session is not None:
            checks.append(_check_session(session))
        checks.extend(
            [
                _check_output_writable(),
                _check_capacity(),
                _check_sandbox(),
            ]
        )
        checks.extend(_check_env_contract())
        checks.append(_check_observability())
        return tuple(
            HealthProbeRecord(
                name=str(c["name"]),
                passed=bool(c["passed"]),
                detail=str(c["detail"]),
                severity=c.get("severity", "ok"),
            )
            for c in checks
        )

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ─── Module-level helpers (private; below the public API for AES403 ordering)


def _env(name: str) -> str:
    """Return a trimmed environment value, or the empty string when unset."""
    return os.environ.get(name, "").strip()


def _flag(name: str) -> bool:
    """Return True when the environment switch is one of the truthy spellings."""
    return _env(name).casefold() in {"1", "true", "yes"}


def _sandbox_unavailable() -> bool:
    """Return True when the host cannot host Chromium's OS sandbox.

    Chromium needs seccomp-bpf or unprivileged user namespaces; a container
    or a hardened host can lack both, and Chromium then refuses to start
    without ``--no-sandbox``. Mirrors the runtime detection in
    ``utility_core_config_factory.sandbox_unavailable`` so the reported
    mode matches the mode the browser actually launches with.
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


def _check_python() -> dict[str, Any]:
    """Report the interpreter version against the supported floor."""
    ok = sys.version_info >= (3, 10)
    return {
        "name": "Python Version",
        "passed": ok,
        "detail": f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (>= 3.10)",
    }


def _check_chromium() -> dict[str, Any]:
    """Report whether a Chromium binary is reachable for Playwright to launch.

    A cache hit or a trusted system binary is enough for the common path.
    """
    from modules.shared.src.update.utility_update_browser_binary import find_chrome_binary

    trusted_binary = find_chrome_binary()
    browsers_dir = playwright_browsers_path()
    if trusted_binary or (browsers_dir.exists() and any(browsers_dir.glob("chromium-*"))):
        detail = "Chromium binary found in Playwright cache or system PATH"
        if _flag("QWEN_DOCTOR_SHOW_PATH"):
            detail = f"{detail}; cache {browsers_dir}"
            if trusted_binary:
                detail = f"{detail}; trusted binary {trusted_binary}"
        return {"name": "Playwright Chromium Browser", "passed": True, "detail": detail}
    return {
        "name": "Playwright Chromium Browser",
        "passed": False,
        "detail": "Chromium binary not found in cache or PATH (run with --deep for a full probe)",
    }


def _check_workspace() -> dict[str, Any]:
    """Report whether ``qwa init`` created the per-directory XDG symlinks."""
    dot_qwen = Path.cwd() / LOCAL_WS_DIR
    ok = dot_qwen.exists() and any((dot_qwen / link).exists() for link in ("log", "output"))
    return {
        "name": "Workspace Initialization",
        "passed": ok,
        "detail": (
            f"Workspace found at {dot_qwen} (per-directory; session/output are global XDG)"
            if ok
            else "Workspace not initialized in this directory (run: qwen-web-arwaky init). "
            "Note: workspaces are per-directory; your login session and outputs are global."
        ),
    }


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
            icon = "●" if s.is_healthy else ("◐" if s.is_limited else "○")
            lines.append(f"  {icon} {s.session_id} ({s.name}): {s.status.value}")
        healthy = sum(1 for s in entries if s.is_healthy)
        limited = sum(1 for s in entries if s.is_limited)
        detail = f"{healthy} healthy, {limited} limited"
        severity = "warning" if healthy == 0 else "ok"
        return {
            "name": "Session Authentication Token",
            "passed": healthy > 0,
            "detail": detail,
            "severity": severity,
        }

    return {
        "name": "Session Authentication Token",
        "passed": False,
        "detail": f"No session in the pool under {SESSIONS_DIR} (run: qwen-web-arwaky session login --name default)",
    }


def _check_output_writable() -> dict[str, Any]:
    """Report whether the XDG output directory accepts writes."""
    try:
        DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
        probe = DEFAULT_OUTPUT / ".doctor_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return {
            "name": "Output Storage Permission",
            "passed": False,
            "detail": f"Output directory not writable ({DEFAULT_OUTPUT}): {exc} (runbook: docs/disk-exhaustion.md)",
        }
    return {
        "name": "Output Storage Permission",
        "passed": True,
        "detail": f"Output directory writable ({DEFAULT_OUTPUT})",
    }


def _check_capacity() -> dict[str, Any]:
    """Report the browser fan-out this host can carry and the source of the limit.

    The limit is derived from available memory rather than a fixed constant,
    so the reported number matches what the job executor will actually use
    (issue #291).
    """
    configured = _env("QWEN_WEB_MAX_WORKERS")
    derived = recommended_max_workers()
    if configured.isdigit():
        oversubscribed = int(configured) > derived
        return {
            "name": "Host Capacity",
            "passed": True,
            "detail": f"host capacity {configured} workers overrides the derived limit {derived}",
            "severity": "warning" if oversubscribed else "ok",
        }
    return {"name": "Host Capacity", "passed": True, "detail": f"host capacity derived as {derived} workers"}


def _check_sandbox() -> dict[str, Any]:
    """Report the effective Chromium sandbox mode and what drove it."""
    if _flag("QWEN_DISABLE_SANDBOX"):
        mode = "disabled (QWEN_DISABLE_SANDBOX)"
        reason = " — every non-login job runs without Chromium's process sandbox"
    elif _sandbox_unavailable():
        mode = "disabled (host has no seccomp filter or user namespaces)"
        reason = " — expected on this host; re-enable by granting seccomp or user namespaces"
    elif _flag("QWEN_ENABLE_SANDBOX"):
        mode = "sandboxed (forced via QWEN_ENABLE_SANDBOX)"
        reason = ""
    else:
        mode = "sandboxed"
        reason = ""
    return {
        "name": "Chromium Sandbox",
        "passed": True,
        "detail": f"Chromium sandbox mode: {mode}{reason}",
        "severity": "warning" if mode.startswith("disabled") else "ok",
    }


def _check_env_contract() -> list[dict[str, Any]]:
    """Report registry validation failures and unrecognized ``QWEN_``/``QWA_`` names.

    A typo'd switch silently selects a different runtime mode, so an unknown
    name is surfaced as a warning naming the registered alternatives
    (issue #292).
    """
    checks: list[dict[str, Any]] = []
    problems = validate_env()
    checks.append(
        {
            "name": "Environment Contract",
            "passed": not problems,
            "detail": (
                "all recognized variables parse cleanly"
                if not problems
                else "; ".join(problems) + " (see .env.example)"
            ),
        }
    )
    unknown = unknown_env_vars()
    if unknown:
        checks.append(
            {
                "name": "Unrecognized Environment Variables",
                "passed": True,
                "detail": (
                    f"set but not in the registry: {', '.join(unknown)} — a typo changes runtime behaviour silently; "
                    f"known names: {', '.join(sorted(effective_config()))}"
                ),
                "severity": "warning",
            }
        )
    return checks


def _check_observability() -> dict[str, Any]:
    """Warn when a production host has no external error tracking configured.

    Both Sentry and OTLP left unset means failures reach only the rotating
    file log, so a production deployment fails silently (issue #297).
    """
    sentry = bool(_env(SENTRY_DSN))
    otlp = bool(_env("OTEL_EXPORTER_OTLP_ENDPOINT"))
    if _env(ENVIRONMENT).casefold() == "production" and not (sentry or otlp):
        return {
            "name": "Observability Backends",
            "passed": True,
            "detail": (
                "ENVIRONMENT=production with SENTRY_DSN and OTEL_EXPORTER_OTLP_ENDPOINT both unset — "
                "errors reach the local file log only (runbook: docs/other.md)"
            ),
            "severity": "warning",
        }
    mode = "Sentry + OTLP" if sentry and otlp else ("Sentry" if sentry else ("OTLP" if otlp else "file log only"))
    return {"name": "Observability Backends", "passed": True, "detail": f"error tracking: {mode}"}


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
    probe = ConfigHealthProbe()
    aggregate = session

    def _gate() -> tuple[tuple[str, bool, str], ...]:
        return tuple((r.name, r.passed, r.detail) for r in probe.probe(session=aggregate))

    return _gate


__all__ = [
    "ConfigHealthProbe",
    "build_smoke_gate",
]
