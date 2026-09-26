"""Core utility: host resource gate for the parallel browser test tier.

Wraps stdlib-only probes with the minimums documented in TEST.md (§7.5a) so
the test suite can decide whether to skip the parallel browser tier. No
external dependency (no psutil, no py-cpuinfo) — ``/proc/meminfo``, ``vm_stat``,
and ``GlobalMemoryStatusEx`` are all reachable from the standard library or the
OS itself.

AES201: stateless functions over the host, no cross-layer imports.
AES404: no class definitions in this utility file; ``probe()`` returns a
mapping so the shape stays an ordinary value.
"""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable, Mapping
from typing import Any

# Minimum host capacity documented in TEST.md for the parallel browser tier.
# 4 GiB / 4 cores is the hard floor; TEST.md recommends 8 GiB.
MIN_RAM_GB = 4.0
MIN_CPU_CORES = 4

_BYTES_PER_GB = 1024**3
_LINUX_MEMINFO_KB = 1024
_DARWIN_PAGE_BYTES = 4096


# ─── Platform probes ─────────────────────────────────────────────────────────


def _probe_ram_gb_linux() -> float | None:
    """Read available RAM from ``/proc/meminfo``; ``None`` when unreadable."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * _LINUX_MEMINFO_KB / _BYTES_PER_GB
    except (OSError, ValueError, IndexError):
        return None
    return None


def _probe_ram_gb_darwin() -> float | None:
    """Read available RAM from ``vm_stat`` free + inactive pages; ``None`` when unavailable."""
    import subprocess  # nosec B404 - fixed argv, no shell

    try:
        result = subprocess.run(  # nosec B603 - fixed argv, no shell
            ["vm_stat"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    free = inactive = 0
    for line in result.stdout.decode("utf-8", errors="replace").splitlines():
        _, _, value = line.partition(".")
        digits = value.strip().rstrip(".")
        if not digits.isdigit():
            continue
        if line.startswith("Pages free"):
            free = int(digits)
        elif line.startswith("Pages inactive"):
            inactive = int(digits)
    if free == 0 and inactive == 0:
        return None
    return (free + inactive) * _DARWIN_PAGE_BYTES / _BYTES_PER_GB


def _probe_ram_gb_windows() -> float | None:
    """Read available RAM via ``GlobalMemoryStatusEx``; ``None`` on non-Windows."""
    if not hasattr(ctypes, "windll"):
        return None

    class _MemoryStatusEx(ctypes.Structure):
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

    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        windll = ctypes.windll  # nosec
        kernel32 = windll.kernel32
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return float(status.ullAvailPhys) / _BYTES_PER_GB
    except (AttributeError, OSError, ValueError):
        return None


_RAM_PROBERS: Mapping[str, Callable[[], float | None]] = {
    "linux": _probe_ram_gb_linux,
    "darwin": _probe_ram_gb_darwin,
    "win32": _probe_ram_gb_windows,
}


def _ram_gb() -> float | None:
    """Dispatch to the platform RAM probe, returning ``None`` when unsupported."""
    prober = _RAM_PROBERS.get(sys.platform)
    if prober is None:
        return None
    return prober()


def _cpu_count() -> int | None:
    """Return the usable CPU count, honouring the scheduler affinity mask."""
    if hasattr(os, "sched_getaffinity"):
        try:
            return len(os.sched_getaffinity(0))
        except OSError:
            pass
    return os.cpu_count()


# ─── Public API ──────────────────────────────────────────────────────────────


def probe() -> Mapping[str, float | int | None]:
    """Return the host's available RAM in GiB and usable CPU count.

    Either value is ``None`` when the platform will not report it, so a caller
    can distinguish "too small" from "cannot tell".
    """
    ram = _ram_gb()
    cpu = _cpu_count()
    return {"ram_gb": ram, "cpu_count": cpu}


def insufficient_reason(resources: Mapping[str, Any] | None = None) -> str | None:
    """Return why the host cannot run the parallel browser tier, else ``None``.

    Unknown values never produce a reason: a platform that will not report its
    memory must not cause the tier to be skipped on every machine.
    """
    observed = resources if resources is not None else probe()
    ram = observed.get("ram_gb")
    cpu = observed.get("cpu_count")
    if isinstance(ram, int | float) and float(ram) < MIN_RAM_GB:
        return f"{float(ram):.1f}GB available RAM (need >={MIN_RAM_GB}GB)"
    if isinstance(cpu, int | float) and float(cpu) < MIN_CPU_CORES:
        return f"{int(cpu)} usable CPU cores (need >={MIN_CPU_CORES})"
    return None


__all__ = ["MIN_CPU_CORES", "MIN_RAM_GB", "insufficient_reason", "probe"]
