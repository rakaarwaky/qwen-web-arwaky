"""Unit tests for utility_core_capacity — host capacity probing (issue #291).

Locks the bound that keeps a 10-browser fan-out from OOM-killing a runner: the
recommended worker count is derived from measured available memory, never
exceeds the constant cap, and never drops below one so a low-memory host
degrades to serial execution.
"""

from __future__ import annotations

from unittest.mock import patch

from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_MAX_WORKERS,
    MIN_MEMORY_PER_WORKER_BYTES,
)
from modules.shared.src.utility_core_capacity import (
    available_memory_bytes,
    describe_capacity,
    format_bytes,
    recommended_max_workers,
    total_memory_bytes,
)

_GIB = 1024**3


def test_worker_budget_is_at_least_700_mib():
    assert MIN_MEMORY_PER_WORKER_BYTES == 700 * 1024 * 1024


def test_recommended_workers_scales_with_available_memory():
    with patch("modules.shared.src.utility_core_capacity.available_memory_bytes", return_value=2 * _GIB):
        assert recommended_max_workers() == 2


def test_recommended_workers_never_exceeds_the_constant_cap():
    with patch("modules.shared.src.utility_core_capacity.available_memory_bytes", return_value=512 * _GIB):
        assert recommended_max_workers() == DEFAULT_MAX_WORKERS


def test_recommended_workers_degrades_to_one_on_a_tiny_host():
    with patch("modules.shared.src.utility_core_capacity.available_memory_bytes", return_value=200 * 1024**2):
        assert recommended_max_workers() == 1


def test_recommended_workers_degrades_to_one_when_memory_is_unreadable():
    with (
        patch("modules.shared.src.utility_core_capacity.available_memory_bytes", return_value=None),
        patch("modules.shared.src.utility_core_capacity.total_memory_bytes", return_value=None),
    ):
        assert recommended_max_workers() == DEFAULT_MAX_WORKERS


def test_recommended_workers_falls_back_to_total_memory_when_available_is_unreadable():
    with (
        patch("modules.shared.src.utility_core_capacity.available_memory_bytes", return_value=0),
        patch("modules.shared.src.utility_core_capacity.total_memory_bytes", return_value=8 * _GIB),
    ):
        # 75% of 8 GiB is 6 GiB, which carries 8 browsers at a 700 MiB budget.
        assert recommended_max_workers() == 8


def test_recommended_workers_on_this_host_is_within_bounds():
    assert 1 <= recommended_max_workers() <= DEFAULT_MAX_WORKERS


def test_available_memory_never_exceeds_total_on_this_host():
    total = total_memory_bytes()
    available = available_memory_bytes()
    if total and available:
        assert available <= total


def test_describe_capacity_reports_the_derived_limit():
    text = describe_capacity()
    assert "recommended max workers" in text
    assert str(recommended_max_workers()) in text


def test_format_bytes_renders_gib_and_mib():
    assert format_bytes(2 * _GIB) == "2.0 GiB"
    assert format_bytes(700 * 1024**2) == "700 MiB"
