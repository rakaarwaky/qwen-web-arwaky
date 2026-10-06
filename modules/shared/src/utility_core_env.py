"""Utility layer (utility_core_env): the single source of truth for environment configuration.

Recognizes every environment variable that changes qwen-web-arwaky behaviour,
with purpose, default, and sensitivity, so an operator can provision a host
from one committed registry (``.env.example``). Secrets and behaviour switches
share one mechanism: the registry labels which is which, and
``effective_config`` masks secret values before they are ever printed
(issue #292).

Registry entries are plain tuples — ``(name, purpose, default, secret)`` —
because the Utility layer holds no type definitions; the field positions are
named by the ``_`` constants below.

The same module owns the operator's *persisted* overrides: a second utility
importing this one would break the layer's no-utility-imports rule.
:func:`install_settings` is called by the CLI entry before the container is
built, so a value chosen in the TUI Settings screen is in force for the run
that reads it. The file holds overrides only — the defaults above keep working
with zero configuration, and an empty field on the screen means "back to the
default", never "set to empty".
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from modules.shared.src.taxonomy_core_constant import XDG_CONFIG_HOME

_MASK = "***"
_GITHUB_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

#: File name under the XDG config home holding the operator's overrides.
SETTINGS_FILE_NAME = "settings.env"

#: Header written above the values so the file explains itself to the next
#: reader, including whoever opens it in an editor a year from now.
_SETTINGS_HEADER = (
    "# qwen-web-arwaky runtime overrides.\n"
    "# Edited by the TUI Settings screen; loaded before the container is built.\n"
    "# Only registered values are honoured. The process environment wins.\n"
)

# Names registered in :data:`REGISTERED_ENV` — one constant per variable so
# call sites never drift from the registry.
ENVIRONMENT = "ENVIRONMENT"
OTEL_EXPORTER_OTLP_ENDPOINT = "OTEL_EXPORTER_OTLP_ENDPOINT"
OTEL_SERVICE_NAME = "OTEL_SERVICE_NAME"
PLAYWRIGHT_BROWSERS_PATH = "PLAYWRIGHT_BROWSERS_PATH"
QWA_SWARM_HEADLESS = "QWA_SWARM_HEADLESS"
QWEN_DEFAULT_MODEL = "QWEN_DEFAULT_MODEL"
QWEN_DISABLE_SANDBOX = "QWEN_DISABLE_SANDBOX"
QWEN_DOCTOR_DEEP = "QWEN_DOCTOR_DEEP"
QWEN_DOCTOR_SHOW_PATH = "QWEN_DOCTOR_SHOW_PATH"
QWEN_ENABLE_SANDBOX = "QWEN_ENABLE_SANDBOX"
QWEN_REQUEST_TIMEOUT_SEC = "QWEN_REQUEST_TIMEOUT_SEC"
QWEN_STREAM_SAFETY_TIMEOUT_SEC = "QWEN_STREAM_SAFETY_TIMEOUT_SEC"
QWEN_SWARM_CONCURRENCY = "QWEN_SWARM_CONCURRENCY"
QWEN_WEB_GITHUB_REPO = "QWEN_WEB_GITHUB_REPO"
QWEN_WEB_MAX_WORKERS = "QWEN_WEB_MAX_WORKERS"
QWEN_WORKSPACE_ROOT = "QWEN_WORKSPACE_ROOT"
SENTRY_DSN = "SENTRY_DSN"

#: Every variable the application reads, as
#: ``(name, purpose, default, secret)`` tuples. ``secret`` marks a value that
#: may carry credentials and must be masked in logs and ``doctor --json``.
REGISTERED_ENV: tuple[tuple[str, str, str, bool], ...] = (
    (ENVIRONMENT, "deployment mode; switches log rendering between console and JSON", "production", False),
    (OTEL_EXPORTER_OTLP_ENDPOINT, "OTLP HTTP endpoint for trace export; empty leaves tracing on no-op", "", False),
    (OTEL_SERVICE_NAME, "service name reported to OpenTelemetry resources", "qwen-web", False),
    (PLAYWRIGHT_BROWSERS_PATH, "override the Playwright browser cache directory", "platform default", False),
    (QWA_SWARM_HEADLESS, "force Swarm browsers headed when '0' or 'false' (default: headless)", "headless", False),
    (QWEN_DEFAULT_MODEL, "model pinned at chat start; empty falls back to Qwen3.8-Max", "Qwen3.8-Max", False),
    (QWEN_DISABLE_SANDBOX, "explicitly drop Chromium's OS sandbox (1/true/yes)", "unset", False),
    (QWEN_DOCTOR_DEEP, "enable the slow Playwright cold-start probe in doctor", "0", False),
    (QWEN_DOCTOR_SHOW_PATH, "print the effective Chromium binary path in doctor", "0", False),
    (QWEN_ENABLE_SANDBOX, "force Chromium's OS sandbox back on even in containers", "unset", False),
    (QWEN_REQUEST_TIMEOUT_SEC, "ceiling on how long a single response may take", "600s", False),
    (QWEN_STREAM_SAFETY_TIMEOUT_SEC, "safety timeout for a streaming response; 0 disables", "4h", False),
    (QWEN_SWARM_CONCURRENCY, "browser fan-out cap for one Swarm; clamped by host memory (issue #291)", "auto", False),
    (
        QWEN_WEB_GITHUB_REPO,
        "owner/repo for update discovery; must match owner/repo form",
        "rakaarwaky/qwen-web-arwaky",
        False,
    ),
    (
        QWEN_WEB_MAX_WORKERS,
        "job-executor worker count; derived from host memory when unset (issue #291)",
        "auto",
        False,
    ),
    (QWEN_WORKSPACE_ROOT, "path boundary for MCP file access", "current directory", False),
    (SENTRY_DSN, "Sentry error tracking DSN; empty leaves error tracking off (issue #297)", "", True),
)

_REGISTERED_NAMES: frozenset[str] = frozenset(entry[0] for entry in REGISTERED_ENV)
_SECRET_NAMES: frozenset[str] = frozenset(entry[0] for entry in REGISTERED_ENV if entry[3])
_DEFAULTS: dict[str, str] = {entry[0]: entry[2] for entry in REGISTERED_ENV}


def registered_env() -> tuple[tuple[str, str, str, bool], ...]:
    """Return the registry entries as ``(name, purpose, default, secret)`` tuples."""
    return REGISTERED_ENV


def is_secret(name: str) -> bool:
    """Return True when *name* is registered as carrying a credential."""
    return name in _SECRET_NAMES


def get_env(name: str) -> str:
    """Return the raw value of *name* (empty string when unset)."""
    return os.environ.get(name, "")


def get_secret_env(name: str) -> str:
    """Return a secret variable's value; raise when *name* is not registered.

    Centralizing secret reads in one place keeps masking consistent: callers
    never format a raw DSN into logs or ``doctor`` output directly.
    """
    if name not in _REGISTERED_NAMES:
        raise KeyError(f"{name!r} is not in the environment registry")
    return os.environ.get(name, "")


def unknown_env_vars(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return ``QWEN_*``/``QWA_*`` variables set but not in the registry.

    A typo'd variable silently produces a different runtime mode (issue #292),
    so doctor surfaces every unrecognized name as a warning.
    """
    source = env if env is not None else os.environ
    unrecognized = [name for name in source if name.startswith(("QWEN_", "QWA_")) and name not in _REGISTERED_NAMES]
    return tuple(sorted(unrecognized))


def effective_config(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the effective value of every registered variable, secrets masked.

    Values fall back to the registry default when unset. The returned mapping
    is safe to print or embed in ``doctor --json`` output: ``SENTRY_DSN`` is
    never echoed raw.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    out: dict[str, str] = {}
    for name, _purpose, default, secret in REGISTERED_ENV:
        value = source.get(name, "").strip()
        out[name] = _MASK if secret and value else value or default
    return out


def runbook_index() -> dict[str, str]:
    """Map ErrorCategory values to the operator runbook that covers them.

    One source of truth for ``doctor`` failure messages and Sentry alert
    deep-links (issue #299).
    """
    return {
        "auth": "docs/runbooks/auth-expiry.md",
        "browser": "docs/runbooks/browser-launch.md",
        "network": "docs/runbooks/network.md",
        "rate_limit": "docs/runbooks/rate-limit.md",
        "response_timeout": "docs/runbooks/response-timeout.md",
        "stuck": "docs/runbooks/stuck.md",
        "file_io": "docs/runbooks/disk-exhaustion.md",
        "session": "docs/runbooks/session-corruption.md",
        "update": "docs/runbooks/update-failure.md",
        "injection": "docs/runbooks/injection.md",
        "parsing": "docs/runbooks/parsing.md",
        "model": "docs/runbooks/model-switch.md",
        "other": "docs/runbooks/other.md",
    }


def validate_env(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Validate provided (or process) environment values; return problems.

    An empty tuple means every provided value for a registered variable is
    parseable. Problems are advisory — the application runs with the effective
    value — but doctor reports them so a mis-typed switch cannot silently
    change runtime behaviour.
    """
    source: Mapping[str, str] = env if env is not None else os.environ
    problems: list[str] = []
    repo = source.get(QWEN_WEB_GITHUB_REPO, "").strip()
    if repo and _GITHUB_REPO.fullmatch(repo) is None:
        problems.append(f"{QWEN_WEB_GITHUB_REPO}: {repo!r} is not an owner/repo path")
    for name in (QWEN_WEB_MAX_WORKERS, QWEN_SWARM_CONCURRENCY):
        raw = source.get(name, "").strip()
        if raw and not raw.isdigit():
            problems.append(f"{name}: {raw!r} is not a positive integer")
    response_ceiling = source.get(QWEN_REQUEST_TIMEOUT_SEC, "").strip()
    if response_ceiling and not response_ceiling.isdigit():
        problems.append(f"{QWEN_REQUEST_TIMEOUT_SEC}: {response_ceiling!r} is not a positive integer")
    timeout = source.get(QWEN_STREAM_SAFETY_TIMEOUT_SEC, "").strip()
    if timeout and (not timeout.isdigit() or int(timeout) < 0):
        problems.append(f"{QWEN_STREAM_SAFETY_TIMEOUT_SEC}: {timeout!r} is not a non-negative integer")
    model = source.get(QWEN_DEFAULT_MODEL, "").strip()
    if model and len(model) > 128:
        problems.append(f"{QWEN_DEFAULT_MODEL}: value exceeds 128 characters")
    workspace = source.get(QWEN_WORKSPACE_ROOT, "").strip()
    if workspace and not Path(workspace).is_absolute():
        problems.append(f"{QWEN_WORKSPACE_ROOT}: {workspace!r} is not an absolute path")
    return tuple(problems)


# ── Persisted overrides ───────────────────────────────────────────────
# The Settings screen writes what the operator changes here. The file is the
# same shape as a shell fragment, so it can be read with ``cat``, edited by
# hand, or pointed at by a test.


def settings_path() -> Path:
    """Return the XDG path the override file lives at."""
    return XDG_CONFIG_HOME / SETTINGS_FILE_NAME


def _rejected(name: str, value: str) -> bool:
    """Return True when the registry would refuse *value* for *name*.

    A value that fails validation is dropped rather than stored, so a restart
    can never behave differently from the session that typed it.
    """
    if is_secret(name) and not value:
        return True
    return bool(validate_env({name: value}))


def parse_settings(text: str) -> dict[str, str]:
    """Return the overrides in *text*, dropping blanks, comments, and bad values.

    A line is ``NAME=VALUE`` for a registered variable. Unknown names are
    ignored: the registry is the contract, and an unregistered key is read by
    no capability.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        name, _, value = entry.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name in _REGISTERED_NAMES:
            out[name] = value
    return {name: value for name, value in out.items() if not _rejected(name, value)}


def load_settings(path: Path | None = None) -> dict[str, str]:
    """Return the stored overrides, or an empty mapping when there is no file.

    A missing file is the zero-config case and is not an error; an unreadable
    one is swallowed too, because refusing to start over a config typo would be
    worse than running on the defaults.
    """
    try:
        text = (path or settings_path()).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    return parse_settings(text)


def save_settings(values: Mapping[str, str], path: Path | None = None) -> Path:
    """Write *values* as the complete override set and return the file path.

    The file is rewritten whole, so an override the operator removes on the
    Settings screen disappears instead of lingering. Invalid entries are
    dropped, leaving the written file equal to what a later load returns.
    """
    target = path or settings_path()
    kept = {name: value for name, value in values.items() if not _rejected(name, value)}
    lines = [_SETTINGS_HEADER]
    lines.extend(f"{name}={kept[name]}" for name in sorted(kept))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def install_settings(path: Path | None = None, *, env: dict[str, str] | None = None) -> dict[str, str]:
    """Load the override file into *env* without overwriting a real export.

    Returns the values actually installed, so the caller can report which
    source is in force. Only names absent from *env* are set: a shell export is
    the operator's most explicit statement of intent and outranks the file.
    """
    target = env if env is not None else os.environ
    installed: dict[str, str] = {}
    for name, value in load_settings(path).items():
        if not value or target.get(name, "").strip():
            continue
        target[name] = value
        installed[name] = value
    return installed


def clear_settings(names: Iterable[str], path: Path | None = None) -> dict[str, str]:
    """Remove *names* from the override file and from the process environment.

    The defaults take over again, which is what Reset means: a value is not
    blanked, it reverts to whatever the registry default is.
    """
    target = path or settings_path()
    drop = set(names)
    remaining = {name: value for name, value in load_settings(target).items() if name not in drop}
    for name in drop:
        os.environ.pop(name, None)
    save_settings(remaining, target)
    return remaining


__all__ = [
    "ENVIRONMENT",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
    "PLAYWRIGHT_BROWSERS_PATH",
    "QWA_SWARM_HEADLESS",
    "QWEN_DEFAULT_MODEL",
    "QWEN_DISABLE_SANDBOX",
    "QWEN_DOCTOR_DEEP",
    "QWEN_DOCTOR_SHOW_PATH",
    "QWEN_ENABLE_SANDBOX",
    "QWEN_REQUEST_TIMEOUT_SEC",
    "QWEN_STREAM_SAFETY_TIMEOUT_SEC",
    "QWEN_SWARM_CONCURRENCY",
    "QWEN_WEB_GITHUB_REPO",
    "QWEN_WEB_MAX_WORKERS",
    "QWEN_WORKSPACE_ROOT",
    "REGISTERED_ENV",
    "SENTRY_DSN",
    "SETTINGS_FILE_NAME",
    "clear_settings",
    "effective_config",
    "get_env",
    "get_secret_env",
    "install_settings",
    "is_secret",
    "load_settings",
    "parse_settings",
    "registered_env",
    "runbook_index",
    "save_settings",
    "settings_path",
    "unknown_env_vars",
    "validate_env",
]
