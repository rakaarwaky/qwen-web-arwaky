"""Utility: telemetry egress scrubbing and private-path hardening.

Utility layer (utility_telemetry_scrubber): stateless functions that decide
what an external telemetry sink is allowed to receive, and what file modes
local forensic artifacts must carry.

Security (issue #352): Sentry and OTLP egress can carry absolute home
directory paths, workspace filenames, and prompt-derived strings inside
exception messages. Everything leaving the host is redacted first. External
telemetry stays opt-in — an empty ``SENTRY_DSN`` or
``OTEL_EXPORTER_OTLP_ENDPOINT`` remains a hard no-op.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

# Owner-only bits: the log and job directories hold per-run forensic artifacts
# and must not be readable by group or other regardless of the process umask.
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600

_HOME_PLACEHOLDER = "<HOME>"
_REDACTED_PLACEHOLDER = "<redacted>"

# Field names whose values are user prompt content or assistant answers. Scraped
# model text is untrusted data and must never be exported verbatim.
_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "prompt",
        "prompt_text",
        "prompttext",
        "input",
        "result",
        "result_text",
        "answer",
        "response_text",
        "content",
        "output",
        "text",
        "message_body",
        "attachment",
        "attachment_file",
    }
)


def _host_path_prefixes() -> tuple[str, ...]:
    """Return the host path prefixes to redact, longest first.

    Longest-first ordering means a nested XDG directory is redacted before its
    parent, so no partially redacted prefix survives.
    """
    prefixes = [str(Path.home())]
    for var in ("XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "TMPDIR"):
        value = os.environ.get(var, "").strip()
        if value:
            prefixes.append(value)
    return tuple(sorted(set(prefixes), key=len, reverse=True))


def redact_host_paths(text: str) -> str:
    """Replace home and XDG directory prefixes in *text* with ``<HOME>``."""
    if not text:
        return text
    for prefix in _host_path_prefixes():
        if prefix in text:
            text = text.replace(prefix, _HOME_PLACEHOLDER)
    return text


def _scrub_value(value: Any) -> Any:
    """Redact host paths inside strings, lists, tuples, and dicts recursively."""
    if isinstance(value, str):
        return redact_host_paths(value)
    if isinstance(value, dict):
        return {key: _scrub_field(key, _scrub_value(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_value(item) for item in value)
    return value


def _scrub_field(key: str, value: Any) -> Any:
    """Replace values whose field name marks them prompt- or answer-derived."""
    if key.lower() in _SENSITIVE_FIELD_NAMES:
        return _REDACTED_PLACEHOLDER
    return value


def scrub_telemetry_event(event: dict[str, Any] | None, _hint: Any = None) -> dict[str, Any] | None:
    """Return a Sentry event safe to transmit, or ``None`` to drop it.

    Applied through Sentry's ``before_send`` hook: absolute home paths are
    redacted, prompt- and answer-derived fields are replaced, and the event
    carries no host or user identity.
    """
    if event is None:
        return None
    scrubbed = _scrub_value(event)
    if not isinstance(scrubbed, dict):
        return None
    scrubbed.pop("user", None)
    scrubbed.pop("server_name", None)
    return scrubbed


def scrub_span_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    """Return OTLP span attributes safe to transmit off-host."""
    if not attributes:
        return {}
    scrubbed = _scrub_value(attributes)
    if not isinstance(scrubbed, dict):
        return {}
    scrubbed.pop("process.command_line", None)
    return scrubbed


def harden_private_dir(path: Path) -> None:
    """Create *path* with owner-only permissions and enforce them against umask.

    ``mkdir(mode=...)`` applies the process umask, so the mode is also applied
    explicitly afterwards to guarantee ``0o700`` regardless of the umask in
    effect. Failures are suppressed: a read-only or foreign-owned state
    directory must not abort observability setup.
    """
    try:
        path.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIR_MODE)
    except OSError:
        return
    with contextlib.suppress(OSError):
        path.chmod(PRIVATE_DIR_MODE)


def harden_private_file(path: Path) -> None:
    """Enforce owner-only read/write on an existing forensic artifact."""
    with contextlib.suppress(OSError):
        path.chmod(PRIVATE_FILE_MODE)


__all__ = [
    "PRIVATE_DIR_MODE",
    "PRIVATE_FILE_MODE",
    "harden_private_dir",
    "harden_private_file",
    "redact_host_paths",
    "scrub_span_attributes",
    "scrub_telemetry_event",
]
