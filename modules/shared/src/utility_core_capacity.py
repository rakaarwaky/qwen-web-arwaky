"""Utility layer (utility_core_capacity): host capacity probing for the browser fleet.

Each concurrent job owns a Chromium process plus an ephemeral clone of the
master session profile. Fanning out on an under-provisioned host OOM-kills
browsers mid-run and leaves orphaned Chromium children, so the effective worker
count is derived from measured host memory instead of a fixed constant
(issue #291). Stateless functions only; taxonomy imports.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_MAX_WORKERS,
    MEMORY_RESERVED_FRACTION,
    MIN_MEMORY_PER_WORKER_BYTES,
)

_MEMINFO = Path("/proc/meminfo")


def total_memory_bytes() -> int | None:
    """Return total physical RAM in bytes, or None when the host cannot report it."""
    if _MEMINFO.is_file():
        return _meminfo_bytes("MemTotal")
    if os.name == "nt":  # pragma: no cover - Windows-specific path
        return _windows_memory(0)
    return None


def available_memory_bytes() -> int | None:
    """Return RAM the kernel can hand out now, or None when it cannot be measured.

    ``MemAvailable`` is the kernel's own estimate of allocatable memory
    including reclaimable page cache, so it is a truer bound on a safe fan-out
    than total RAM. Kernels without that field fall back to ``MemFree``.
    """
    if _MEMINFO.is_file():
        return _meminfo_bytes("MemAvailable") or _meminfo_bytes("MemFree")
    if os.name == "nt":  # pragma: no cover - Windows-specific path
        return _windows_memory(1)
    return None


def recommended_max_workers() -> int:
    """Return how many browsers this host can carry, clamped to 1..DEFAULT_MAX_WORKERS.

    One worker is always allowed so a low-memory host degrades to serial
    execution instead of refusing to run. When memory is unmeasurable the
    constant cap applies unchanged, preserving the previous behaviour.
    """
    budget = available_memory_bytes()
    if not budget or budget <= 0:
        total = total_memory_bytes()
        if not total or total <= 0:
            return DEFAULT_MAX_WORKERS
        budget = int(total * (1.0 - MEMORY_RESERVED_FRACTION))
    return min(DEFAULT_MAX_WORKERS, max(1, int(budget) // MIN_MEMORY_PER_WORKER_BYTES))


def describe_capacity() -> str:
    """Return a one-line operator summary of measured capacity and derived limit."""
    total = total_memory_bytes()
    available = available_memory_bytes()
    total_text = format_bytes(total) if total else "unknown"
    available_text = format_bytes(available) if available else "unknown"
    return (
        f"{total_text} total / {available_text} available; "
        f"recommended max workers {recommended_max_workers()} "
        f"({format_bytes(MIN_MEMORY_PER_WORKER_BYTES)} budget per browser, cap {DEFAULT_MAX_WORKERS})"
    )


def format_bytes(value: int) -> str:
    """Render a byte count as MiB or GiB for operator-facing messages."""
    mib = value / (1024 * 1024)
    if mib >= 1024:
        return f"{mib / 1024:.1f} GiB"
    return f"{mib:.0f} MiB"


def _meminfo_bytes(field: str) -> int | None:
    """Return one ``/proc/meminfo`` field converted from KiB to bytes."""
    try:
        content = _MEMINFO.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in content.splitlines():
        if not line.startswith(f"{field}:"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1]) * 1024
    return None


def _windows_memory(index: int) -> int | None:  # pragma: no cover - Windows-specific path
    """Read total (index 0) or available (index 1) RAM via ``GlobalMemoryStatusEx``."""
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    kernel32 = getattr(ctypes, "windll", None)
    if kernel32 is None or not kernel32.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int((status.ullTotalPhys, status.ullAvailPhys)[index])


__all__ = [
    "MIN_MEMORY_PER_WORKER_BYTES",
    "available_memory_bytes",
    "describe_capacity",
    "format_bytes",
    "recommended_max_workers",
    "total_memory_bytes",
]
