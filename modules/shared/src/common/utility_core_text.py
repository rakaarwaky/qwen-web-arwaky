"""Text-formatting pure utilities: UI-noise stripping and UTC timestamp.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from datetime import datetime, timezone

UI_NOISE_TOKENS = (
    "?",
    "Qwen3",
    "Qwen3.8-Max",
    "Qwen Plus",
    "Qwen Max",
    "Qwen Turbo",
    "Auto",
)


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-format string."""
    return datetime.now(tz=timezone.utc).isoformat()


def strip_ui_noise(text: str) -> str:
    """Remove Qwen UI chrome from the start of captured output."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in UI_NOISE_TOKENS:
            continue
        if stripped.endswith((".md", " KB", " B")):
            continue
        return "\n".join(lines[i:])
    return text
