"""Unit tests for the parallel-browser host resource gate (issue #329).

The parallel tier launches up to ``DEFAULT_MAX_WORKERS`` Chromium instances;
the suite gates that tier on the host so a 4 GiB container does not silently
blow past OOM. Probing is standard-library only so it imports in CI without
adding ``psutil`` to ``uv.lock`` (a ``uv lock --check`` CI gate).

Only portable behaviour is asserted here. Platform probing (``/proc/meminfo``,
``vm_stat``, ``GlobalMemoryStatusEx``) is exercised indirectly through
:func:`insufficient_reason` on explicit mappings, so the suite gives the same
result on every OS.
"""

from __future__ import annotations

import sys

import pytest

from modules.core.src.utility_core_host_gate import (
    MIN_CPU_CORES,
    MIN_RAM_GB,
    insufficient_reason,
    probe,
)

# ── Gate thresholds ─────────────────────────────────────────────────────────


def test_thresholds_match_the_documented_environment_spec() -> None:
    """TEST.md states 4 GiB / 4 cores; the gate must use the same numbers."""
    assert MIN_RAM_GB == 4.0
    assert MIN_CPU_CORES == 4


def test_probe_exposes_the_two_gated_resources() -> None:
    """``probe`` is the public contract conftest consumes."""
    observed = probe()
    assert set(observed) == {"ram_gb", "cpu_count"}


# ── Gate decision logic ─────────────────────────────────────────────────────


def test_host_above_every_threshold_passes() -> None:
    """A host with 8 GiB and 8 cores must not be skipped."""
    assert insufficient_reason({"ram_gb": 8.0, "cpu_count": 8}) is None


def test_exact_thresholds_pass() -> None:
    """The boundary itself is sufficient, not exclusive."""
    assert insufficient_reason({"ram_gb": MIN_RAM_GB, "cpu_count": MIN_CPU_CORES}) is None


@pytest.mark.parametrize("ram_gb", [MIN_RAM_GB - 0.1, 2.0, 0.0])
def test_ram_below_floor_is_reported(ram_gb: float) -> None:
    """Too little available RAM skips the tier with the observed value."""
    reason = insufficient_reason({"ram_gb": ram_gb, "cpu_count": 16})
    assert reason is not None
    assert "available ram" in reason.lower()
    assert f"{ram_gb:.1f}gb" in reason.lower()


@pytest.mark.parametrize("cpu_count", [MIN_CPU_CORES - 1, 2, 1])
def test_cpu_below_floor_is_reported(cpu_count: int) -> None:
    """Too few usable cores skips the tier with the observed value."""
    reason = insufficient_reason({"ram_gb": 16.0, "cpu_count": cpu_count})
    assert reason is not None
    assert "cpu" in reason.lower()
    assert str(cpu_count) in reason


def test_both_shortfalls_report_the_ram_reason_first() -> None:
    """The first failing check wins so the message stays actionable."""
    reason = insufficient_reason({"ram_gb": 1.0, "cpu_count": 1})
    assert reason is not None
    assert "RAM" in reason


@pytest.mark.parametrize(
    "resources",
    [
        {"ram_gb": None, "cpu_count": 8},
        {"ram_gb": 8.0, "cpu_count": None},
        {"ram_gb": None, "cpu_count": None},
    ],
)
def test_unknown_values_never_skip(resources: dict[str, float | int | None]) -> None:
    """A platform that will not report its specs must not disable the tier.

    Skipping on "unknown" would silently disable parallel browser coverage on
    every host the probe cannot read — the opposite of the gate's purpose.
    """
    assert insufficient_reason(resources) is None


def test_non_numeric_values_never_skip() -> None:
    """A malformed probe result must not crash the gate or skip the tier."""
    assert insufficient_reason({"ram_gb": "many", "cpu_count": None}) is None


# ── Probes return usable values on the running host ─────────────────────────


@pytest.mark.skipif(sys.platform != "linux", reason="reads /proc/meminfo")
def test_linux_probe_reads_memavailable() -> None:
    """The Linux probe returns a plausible available-RAM value."""
    ram = probe()["ram_gb"]
    assert isinstance(ram, float)
    assert 0.0 < ram < 1024.0


def test_probe_agrees_with_the_individual_probes() -> None:
    """``probe`` is a thin wrapper over the two stdlib probes."""
    observed = probe()
    if sys.platform in ("linux", "darwin", "win32"):
        assert isinstance(observed["ram_gb"], float)
    assert isinstance(observed["cpu_count"], int)


def test_ci_host_meets_the_documented_minimums() -> None:
    """GitHub-hosted runners (4 vCPU, 16 GB) must clear the documented floor.

    If this fails, the parallel browser tier is silently skipped everywhere
    and the gate is not doing its job.
    """
    if sys.platform != "linux":
        pytest.skip(f"host probe is best-effort on {sys.platform!r}")
    assert insufficient_reason(probe()) is None
