"""Benchmark for config path resolution.

Uses time.perf_counter for measuring performance without requiring the
pytest-benchmark plugin. Deterministic and filesystem-local: the paths are
created under a temporary directory, so the benchmark needs no network and
no live session.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from modules.config.src.capabilities_config_path_resolver import ConfigPathResolver
from modules.shared.src.taxonomy_core_vo import AppConfig

pytestmark = pytest.mark.benchmark


def bench_resolve_paths(iterations: int = 200) -> float:
    """Benchmark resolving a full path set against a real directory."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "in.md").write_text("prompt", encoding="utf-8")
        resolver = ConfigPathResolver()
        config = AppConfig(
            mode="single",
            input_path=root / "in.md",
            output_path=root / "out.md",
            session_path=root / "session",
        )

        start = time.perf_counter()
        for _ in range(iterations):
            resolver.resolve_paths(config)
        elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000


def test_bench_resolve_paths() -> None:
    """Report benchmark results for path resolution."""
    micros = bench_resolve_paths()
    print(f"\n[BENCHMARK] resolve_paths: {micros:.2f} µs/call")
    assert micros > 0
