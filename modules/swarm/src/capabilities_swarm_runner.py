"""Capabilities: start a Swarm fan-out (AES403).

Implements ISwarmStartProtocol.

One file per protocol seam. This file owns ``ISwarmStartProtocol`` — the
fan-out engine's start seam: discovering the role templates, creating the
Swarm directory, scheduling one leg per role, and running each leg with
the retry policy bounded by the host's circuit breaker and rate limiter.

The snapshot store, the cancel events, and the executor all live in the
shared registry this seam is handed; the progress and cancel seams read the
same registry, so all three observe one fan-out without any of them
importing another. The stateless helpers live in
``utility_swarm_runner_base``.
"""

from __future__ import annotations

import contextvars
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from modules.shared.src.common.taxonomy_core_constant import MAX_ATTEMPTS, SWARM_OUTPUT_ROOT
from modules.shared.src.common.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.common.taxonomy_core_vo import FilePath, HeadlessFlag
from modules.shared.src.common.utility_core_capacity import recommended_max_workers
from modules.shared.src.common.utility_core_prompt_template import (
    list_prompt_templates,
    materialize_role_template,
)
from modules.shared.src.common.utility_response_normalizer import detect_processing_failure
from modules.shared.src.prompt.contract_prompt_aggregate import IPromptAggregate
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse
from modules.shared.src.swarm.contract_swarm_protocol import (
    ISwarmRegistryProtocol,
    ISwarmStartProtocol,
)
from modules.shared.src.swarm.taxonomy_swarm_vo import (
    AgentStatus,
    BrowserCount,
    SwarmAgentSnapshot,
    SwarmId,
    SwarmSnapshot,
)
from modules.shared.src.swarm.utility_swarm_runner_base import (
    CANCELLED_ERROR,
    is_retryable,
    mark_agent_progress,
    new_swarm_id,
    replace_status,
)

log = logging.getLogger(__name__)


# ─── Block 1: Class Definition & Constructor ────────────
class SwarmRunner(ISwarmStartProtocol):
    """Start a fan-out of every discovered role template over one attachment.

    The runner owns the mechanics of a fan-out and nothing else: it does
    not read a request, it does not decide what a folder input means, and
    it does not shape a response for a consumer. Those belong to
    ``SwarmOrchestrator``.
    """

    def __init__(
        self,
        attachment: IPromptAggregate,
        registry: ISwarmRegistryProtocol,
        output_root: Path = SWARM_OUTPUT_ROOT,
        browser_concurrency: int | None = None,
        max_attempts: int = MAX_ATTEMPTS,
        headless: bool = True,
        circuit_breaker: CircuitBreaker | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Wire the fan-out engine to the attachment aggregate it fans out over.

        ``attachment`` is the single material every role reads. ``registry``
        is the shared store the progress and cancel seams read the same run
        from. The host capacity is the ceiling for a fan-out: an explicit
        request above it is clamped so a Swarm cannot OOM the runner
        (issue #291).
        """
        self._attachment = attachment
        self._registry = registry
        self._output_root = Path(output_root)
        self._headless = bool(headless)
        self._headless_for_run = bool(headless)
        if browser_concurrency is None:
            swarm_env = os.environ.get("QWA_SWARM_CONCURRENCY", "").strip()
            concurrency = int(swarm_env) if swarm_env.isdigit() and int(swarm_env) > 0 else recommended_max_workers()
        else:
            concurrency = int(browser_concurrency)
        self._browser_concurrency = min(recommended_max_workers(), max(1, concurrency))
        self._max_attempts = max(1, int(max_attempts))
        self._circuit_breaker = circuit_breaker
        self._rate_limiter = rate_limiter

    @property
    def browser_concurrency(self) -> BrowserCount:
        """Configured browser concurrency for a single Swarm run."""
        return BrowserCount(self._browser_concurrency)

    def start(
        self,
        input_path: FilePath,
        attachment_path: FilePath,
        headless: bool = True,
    ) -> SwarmSnapshot:
        """Create a Swarm directory and schedule all discovered templates.

        ``input_path`` is what the user pointed at and is recorded on the
        snapshot; ``attachment_path`` is the single material every role
        reads. The caller resolves a folder input down to one attachment
        before calling, because the agent threads below are submitted
        immediately and read this path on their first pass.
        """
        source = Path(input_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Swarm input does not exist: {source}")
        roles = list_prompt_templates()
        if not roles:
            raise RuntimeError("No prompt templates were discovered")
        swarm_id = SwarmId(new_swarm_id())
        root = self._output_root / swarm_id
        root.mkdir(parents=True, exist_ok=False)
        snapshot = SwarmSnapshot(
            swarm_id=swarm_id,
            input_path=source,
            root_path=root,
            status="queued",
            max_attempts=self._max_attempts,
            browser_concurrency=self._browser_concurrency,
            agents=tuple(
                SwarmAgentSnapshot(agent_id=role, status="queued", output_path=root / role / "output.md")
                for role in roles
            ),
        )
        self._registry.open_run(
            snapshot,
            {role: threading.Event() for role in roles},
            FilePath(attachment_path),
        )
        executor = ThreadPoolExecutor(
            max_workers=self._browser_concurrency,
            thread_name_prefix=f"qwen_swarm_{swarm_id[-6:]}",
        )
        self._registry.attach_executor(swarm_id, executor)
        self._headless_for_run = bool(headless)
        running = self._registry.revise(swarm_id, lambda current: replace_status(current, "running"))
        for role in roles:
            executor.submit(self._run_agent, swarm_id, role)
        return running or snapshot

    def _update_agent(
        self,
        swarm_id: SwarmId,
        role: str,
        status: AgentStatus,
        attempt: int,
        output_path: Path,
        error: str | None,
        started: float,
    ) -> None:
        """Update one leg's status in the shared snapshot and persist the manifest."""
        self._registry.revise(
            swarm_id,
            lambda current: mark_agent_progress(
                current,
                role,
                status,
                attempt,
                output_path,
                error,
                round(time.perf_counter() - started, 2),
            ),
        )

    def _run_agent(self, swarm_id: SwarmId, role: str) -> None:
        """Execute one fan-out leg with retries, bounded by the cancel event.

        Runs under an isolated contextvars copy so each leg sees its own
        ``_TARGET_MODEL`` (and other contextvars) rather than a sibling leg's
        overrides from ``ThreadPoolExecutor`` context inheritance (ARCH-2-001).
        """
        ctx = contextvars.copy_context()
        ctx.run(self._run_agent_isolated, swarm_id, role)

    def _run_agent_isolated(self, swarm_id: SwarmId, role: str) -> None:
        start = time.perf_counter()
        events = self._registry.cancel_events(swarm_id)
        event = events.get(role)
        attachment_path = self._registry.attachment(swarm_id)
        output_path = self._output_root / swarm_id / role / "output.md"
        last_error = "Unknown Swarm agent failure"
        if event is None or attachment_path is None:
            self._update_agent(swarm_id, role, "cancelled", 0, output_path, CANCELLED_ERROR, start)
            return
        for attempt in range(1, self._max_attempts + 1):
            if event.is_set():
                self._update_agent(swarm_id, role, "cancelled", attempt - 1, output_path, CANCELLED_ERROR, start)
                return
            if self._circuit_breaker is not None and self._circuit_breaker.is_tripped:
                # The breaker only gates the agent in front of it: siblings keep
                # their in-flight browsers, so the swarm ends partial, not aborted.
                self._update_agent(
                    swarm_id,
                    role,
                    "failed",
                    attempt - 1,
                    output_path,
                    "Swarm paused: too many recent failures tripped the circuit breaker",
                    start,
                )
                return
            if self._rate_limiter is not None:
                wait_sec = self._rate_limiter.try_acquire()
                if wait_sec is not None:
                    self._update_agent(
                        swarm_id, role, "running" if attempt == 1 else "retrying", attempt, output_path, None, start
                    )
                    if event.wait(wait_sec):
                        self._update_agent(
                            swarm_id, role, "cancelled", attempt - 1, output_path, CANCELLED_ERROR, start
                        )
                        return
            self._update_agent(
                swarm_id, role, "running" if attempt == 1 else "retrying", attempt, output_path, None, start
            )
            try:
                prompt_file = materialize_role_template(role)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                resp: PromptResponse = self._attachment.execute(
                    PromptRequest(
                        verb="process_prompt_with_attachment",
                        prompt_file=prompt_file,
                        attachment_file=attachment_path,
                        output_file=output_path,
                        headless=HeadlessFlag(self._headless_for_run),
                        cancel_event=event,
                    )
                )
                result_text = resp.response_text or ""
                if detect_processing_failure(result_text):
                    last_error = result_text
                    if self._circuit_breaker is not None:
                        self._circuit_breaker.record_failure()
                    if not is_retryable(last_error) or attempt == self._max_attempts:
                        self._update_agent(swarm_id, role, "failed", attempt, output_path, last_error, start)
                        return
                    continue
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_success()
                self._update_agent(swarm_id, role, "completed", attempt, output_path, None, start)
                return
            except Exception as exc:
                last_error = str(exc)
                if event.is_set():
                    self._update_agent(swarm_id, role, "cancelled", attempt, output_path, CANCELLED_ERROR, start)
                    return
                if self._circuit_breaker is not None:
                    self._circuit_breaker.record_failure()
                if not is_retryable(last_error) or attempt == self._max_attempts:
                    self._update_agent(swarm_id, role, "failed", attempt, output_path, last_error, start)
                    return
        self._update_agent(swarm_id, role, "failed", self._max_attempts, output_path, last_error, start)


__all__ = ["SwarmRunner"]
