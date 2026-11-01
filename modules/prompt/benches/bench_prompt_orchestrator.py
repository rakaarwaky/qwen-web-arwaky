"""Benchmark for prompt orchestrator verb routing.

Uses time.perf_counter for measuring performance without requiring pytest-benchmark plugin.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from modules.prompt.src.agent_prompt_orchestrator import PromptOrchestrator
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse, ResponseText


def _orchestrator() -> PromptOrchestrator:
    """A prompt aggregate wired to one stub per pipeline, as the container builds it."""
    direct = MagicMock()
    file_only = MagicMock()
    attachment = MagicMock()
    for stub in (direct, file_only, attachment):
        stub.execute.return_value = PromptResponse(response_text=ResponseText("The answer"))
    return PromptOrchestrator(
        direct=direct,
        file_only=file_only,
        attachment=attachment,
        cancel_registry=MagicMock(),
        observability=MagicMock(),
    )


def bench_execute_routes_a_direct_prompt(iterations: int = 1000) -> float:
    """Benchmark verb dispatch through the aggregate's single door."""
    orchestrator = _orchestrator()
    request = PromptRequest(verb="process_direct_prompt", prompt_file="prompt.md")

    start = time.perf_counter()
    for _ in range(iterations):
        orchestrator.execute(request)
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def bench_execute_resolves_a_cancel(iterations: int = 1000) -> float:
    """Benchmark the cancel route through the shared registry."""
    orchestrator = _orchestrator()
    request = PromptRequest(verb="request_cancel", cancel_event=threading.Event())

    start = time.perf_counter()
    for _ in range(iterations):
        orchestrator.execute(request)
    elapsed = time.perf_counter() - start
    return elapsed / iterations * 1_000_000  # microseconds per call


def test_bench_execute_routes_a_direct_prompt() -> None:
    """Report benchmark results for verb routing."""
    micros = bench_execute_routes_a_direct_prompt()
    print(f"\n[BENCHMARK] PromptOrchestrator.execute (direct): {micros:.2f} μs/call")
    assert micros > 0


def test_bench_execute_resolves_a_cancel() -> None:
    """Report benchmark results for the cancel route."""
    micros = bench_execute_resolves_a_cancel()
    print(f"\n[BENCHMARK] PromptOrchestrator.execute (cancel): {micros:.2f} μs/call")
    assert micros > 0
