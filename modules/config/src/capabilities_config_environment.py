"""Capabilities: config environment (AES403).

Implements ``IConfigEnvironmentProtocol``.

Centralises every env-derived policy decision the application makes, so the
value the runtime uses and the value a diagnostic reports come from one
probe. Before this seam the container read ``QWEN_WEB_MAX_WORKERS`` and the
Swarm caps directly, and the doctor reimplemented the sandbox probe that
``build_app_config`` already ran.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from modules.shared.src.contract_config_protocol import IConfigEnvironmentProtocol
from modules.shared.src.taxonomy_config_vo import ModelName, SandboxReport, WorkerCount
from modules.shared.src.taxonomy_core_constant import DEFAULT_MAX_WORKERS
from modules.shared.src.taxonomy_core_vo import TimeoutSec
from modules.shared.src.utility_core_capacity import recommended_max_workers
from modules.shared.src.utility_core_env import (
    QWA_SWARM_HEADLESS,
    QWEN_DEFAULT_MODEL,
    QWEN_DISABLE_SANDBOX,
    QWEN_ENABLE_SANDBOX,
    QWEN_SWARM_CONCURRENCY,
    QWEN_WEB_MAX_WORKERS,
)

_TRUE_VALUES = frozenset({"1", "true", "yes"})
_FALSE_VALUES = frozenset({"0", "false", "no"})

#: Built-in ceiling on the response-wait when no env override is present.
#: Matches the default carried by ``AppConfig`` so a bare probe and a built
#: config never diverge.
DEFAULT_REQUEST_TIMEOUT_SEC = 600
REQUEST_TIMEOUT_ENV = "QWEN_REQUEST_TIMEOUT_SEC"


def _env(name: str) -> str:
    """Return a trimmed environment value, or the empty string when unset."""
    return os.environ.get(name, "").strip()


def _flag(name: str) -> bool:
    """Return True when the env switch is one of the truthy spellings."""
    return _env(name).casefold() in _TRUE_VALUES


def _sandbox_host_unavailable() -> bool:
    """Return True when the host cannot provide Chromium's OS sandbox.

    Chromium needs seccomp-bpf and unprivileged user namespaces; a
    container or a hardened host can lack either, in which case Chromium
    refuses to start unless ``--no-sandbox`` is passed (issue #290).
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


def _resolve_request_timeout() -> int:
    """Resolve the response-wait ceiling from the env override or the default."""
    raw = _env(REQUEST_TIMEOUT_ENV)
    if not raw:
        return DEFAULT_REQUEST_TIMEOUT_SEC
    parsed = int(raw) if raw.isdigit() else 0
    return parsed if parsed > 0 else DEFAULT_REQUEST_TIMEOUT_SEC


class ConfigEnvironment(IConfigEnvironmentProtocol):
    """Probe the operator's environment into the values config obeys."""

    def sandbox_report(self) -> SandboxReport:
        """Return the sandbox verdict, with the deciding env switch named.

        Precedence matches what the browser actually launches with: an
        explicit disable outranks an explicit enable, and either one
        outranks host detection. ``QWEN_ENABLE_SANDBOX`` therefore wins
        on a host that reports no seccomp filter, which is the case it
        exists for.
        """
        host_unavailable = _sandbox_host_unavailable()
        if _flag(QWEN_DISABLE_SANDBOX):
            return SandboxReport(
                state="disabled_by_env",
                reason=f"{QWEN_DISABLE_SANDBOX} is set",
                host_supports_sandbox=not host_unavailable,
            )
        if _flag(QWEN_ENABLE_SANDBOX):
            return SandboxReport(
                state="forced",
                reason=f"{QWEN_ENABLE_SANDBOX} forces the sandbox on",
                host_supports_sandbox=True,
            )
        if host_unavailable:
            return SandboxReport(
                state="disabled_by_host",
                reason="host has no seccomp filter or user namespaces",
                host_supports_sandbox=False,
            )
        return SandboxReport(
            state="sandboxed",
            reason="OS sandbox enabled by default",
            host_supports_sandbox=True,
        )

    def request_timeout_sec(self) -> TimeoutSec:
        """Return the response-wait ceiling in force, honouring the env override."""
        return TimeoutSec(_resolve_request_timeout())

    def max_workers(self) -> WorkerCount:
        """Return the job-executor worker count, env override over the memory cap."""
        override = _env(QWEN_WEB_MAX_WORKERS)
        if override.isdigit() and int(override) > 0:
            return WorkerCount(int(override))
        return WorkerCount(recommended_max_workers())

    def swarm_concurrency(self) -> WorkerCount:
        """Return the Swarm browser fan-out cap, clamped to the job-executor cap."""
        override = _env(QWEN_SWARM_CONCURRENCY)
        if override.isdigit() and int(override) > 0:
            return WorkerCount(min(int(override), DEFAULT_MAX_WORKERS))
        return WorkerCount(recommended_max_workers())

    def swarm_headless(self) -> bool:
        """Return whether Swarm browsers run headless (headless unless '0'/'false')."""
        value = _env(QWA_SWARM_HEADLESS).casefold()
        return value not in _FALSE_VALUES

    def model(self) -> ModelName:
        """Return the pinned model, or the empty string for the host default."""
        return ModelName(_env(QWEN_DEFAULT_MODEL))


__all__ = [
    "ConfigEnvironment",
    "DEFAULT_REQUEST_TIMEOUT_SEC",
    "REQUEST_TIMEOUT_ENV",
]
