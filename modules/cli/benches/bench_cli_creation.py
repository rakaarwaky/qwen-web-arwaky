"""Benchmark tests for CLI module — performance measurement using pytest-benchmark."""

from __future__ import annotations

import pytest


@pytest.mark.benchmark
class TestCLIBenchmarks:
    """Benchmark tests for CLI module performance."""

    def test_cli_entry_import_benchmark(self, benchmark):
        """Benchmark CLI main entry import."""
        def import_cli():
            from modules.root_cli_main_entry import main
            return main
        benchmark(import_cli)

    def test_mcp_entry_import_benchmark(self, benchmark):
        """Benchmark MCP entry import."""
        def import_mcp():
            from modules.root_mcp_main_entry import run_mcp_server
            return run_mcp_server
        benchmark(import_mcp)

    def test_tui_app_creation_benchmark(self, benchmark):
        """Benchmark TUI app creation."""
        from modules.cli.src.surface_cli_tui_app import TuiApp

        def create_tui():
            return TuiApp()

        benchmark(create_tui)
