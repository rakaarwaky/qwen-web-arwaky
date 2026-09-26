"""Capabilities: stream monitor (AES403).

Implements IStreamProtocol.
"""

from __future__ import annotations

import contextlib
import os
import threading
import time

from playwright.sync_api import Error, Page

from modules.core.src.utility_core_dom_helper import is_any_visible
from modules.core.src.utility_core_dom_query import latest_message_text
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import IStreamProtocol
from modules.shared.src.taxonomy_core_constant import (
    STOP_BUTTON_SELECTORS,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_error import (
    AuthRequiredError,
    OutputValidationError,
    ResponseDetectionTimeoutError,
    RunCancelledError,
    StuckDetectedError,
)
from modules.shared.src.taxonomy_core_event import (
    EVENT_GENERATION_FINISHED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
)
from modules.shared.src.taxonomy_core_vo import (
    MinTextLength,
    PollIntervalSec,
    ResponseText,
    StabilityChecks,
    StreamerConfig,
)
from modules.shared.src.utility_core_events import is_stability_satisfied, should_treat_as_new_response
from modules.shared.src.utility_core_validation import validate_response_content

log = get_logger("capabilities_stream_monitor")
# Test seam: patched by unit_capability_stream_monitor to script DOM responses.
_dom_latest = latest_message_text
DEFAULT_SAFETY_TIMEOUT_SEC = 4 * 60 * 60
# Event-driven stall threshold: if no forward event (thinking, streaming text
# change, or terminal completion) arrives within this window, the run is
# classified stuck. Slow-but-alive generations keep emitting events and are
# never misclassified. This is not a wall-clock cutoff for generation.
DEFAULT_STALL_TIMEOUT_SEC = 300
# Issue #330: the absolute backstop is operator-tunable without a code change
# (a 4h hardcoded budget is untestable in staging and unusable where hosts
# have tighter wall-clock limits).
SAFETY_TIMEOUT_ENV = "QWEN_STREAM_SAFETY_TIMEOUT_SEC"


def _resolve_safety_timeout(override: int | None) -> int:
    """Resolve the safety circuit-breaker budget.

    Precedence: explicit ``safety_timeout_sec`` constructor argument →
    ``QWEN_STREAM_SAFETY_TIMEOUT_SEC`` env var → the 4-hour default.
    Unparseable or non-positive env values fall back to the default with a
    warning instead of crashing the pipeline boot.
    """
    if override is not None:
        return int(override)
    raw = os.environ.get(SAFETY_TIMEOUT_ENV, "").strip()
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return parsed
        log.warning("Ignoring invalid %s=%r; using default %ds", SAFETY_TIMEOUT_ENV, raw, DEFAULT_SAFETY_TIMEOUT_SEC)
    return DEFAULT_SAFETY_TIMEOUT_SEC


# Block 1: Class Definition & Constructor


class StreamMonitor(IStreamProtocol):
    """Response streaming detection and stability polling."""

    def __init__(
        self,
        config: StreamerConfig | None = None,
        *,
        safety_timeout_sec: int | None = None,
        stall_timeout_sec: int = DEFAULT_STALL_TIMEOUT_SEC,
    ) -> None:
        resolved_safety = _resolve_safety_timeout(safety_timeout_sec)
        if resolved_safety <= 0:
            raise ValueError("safety_timeout_sec must be greater than zero")
        if stall_timeout_sec <= 0:
            raise ValueError("stall_timeout_sec must be greater than zero")
        self.safety_timeout_sec = resolved_safety
        self.stall_timeout_sec = int(stall_timeout_sec)
        if config is not None:
            self.polling_interval_sec = PollIntervalSec(config.polling_interval_sec)
            self.stability_checks = StabilityChecks(config.stability_checks)
            self.min_text_length = MinTextLength(config.min_text_length)
        else:
            self.polling_interval_sec = PollIntervalSec(1.0)
            self.stability_checks = StabilityChecks(4)
            self.min_text_length = MinTextLength(1)

    # ─── Block 2: Public Contract (IStreamProtocol ONLY) ──
    def is_generation_complete(self, page: Page, *, thinking: bool | None = None) -> bool:
        """Check if Qwen AI is done generating.

        Args:
            page: Active Playwright page.
            thinking: Pre-computed ``is_thinking_active`` result for this poll
                cycle. Pass it to avoid a second, redundant JS evaluation (and
                Chromium IPC round-trip) per slot per cycle; omit it to have the
                thinking state resolved on demand.

        """
        try:
            if is_any_visible(page, STOP_BUTTON_SELECTORS):
                return False
            if thinking is None:
                thinking = self.is_thinking_active(page)
            return not thinking
        except Exception:
            return False

    def is_thinking_active(self, page: Page) -> bool:
        """Check whether Qwen's live thinking/status indicator is visible.

        Scans every thinking/status-card element (not just the first) and only
        reports active when at least one visible element's text says "thinking"
        without a completed/complete marker. A finished card that stays in the
        DOM (e.g. "Thinking completed") must NOT count as active.
        """
        try:
            js_check = """
                () => {
                  const els = document.querySelectorAll('[class*="thinking"], [class*="status-card"],
                    [class*="typing"], [class*="streaming"]');
                  for (const el of els) {
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 && r.height === 0) continue;
                    const txt = (el.innerText || '').toLowerCase();
                    if (txt.includes('thinking') && !txt.includes('completed') && !txt.includes('complete'))
                      return true;
                  }
                  return false;
                }
            """
            return bool(page.evaluate(js_check))
        except Exception:
            return False

    def wait_for_response(
        self,
        page: Page,
        timeout_sec: int,
        msg_count_before: int,
        emitter: LifecycleEmitter,
        polling_interval_sec: float = 1.0,
        stability_checks: int = 4,
        min_text_length: int = 1,
        dispatch_acknowledged: bool = True,
        baseline_text: ResponseText | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ResponseText | None:
        """Wait for a terminal assistant response using event-driven DOM signals.

        ``timeout_sec`` is a **hard cutoff** (issue #372), matching the
        MCP/CLI contract wording ("maximum seconds to wait for the assistant
        response"): when the elapsed wait exceeds it without a terminal
        generation event, a ``ResponseDetectionTimeoutError`` is raised so the
        caller's dispatch loop can retry or fail the run. The loop otherwise
        exits on a terminal generation event (stable response plus a
        completed generation state).

        Failure detection is event-driven inside the budget: the monitor
        tracks the last *forward event* (thinking started, streamed text
        change, or terminal completion). When no forward event arrives within
        ``stall_timeout_sec``, a ``StuckDetectedError`` is raised so callers
        can retry. Slow-but-alive generations keep emitting forward events
        and are never misclassified as stuck — but they are still bounded by
        the ``timeout_sec`` hard cutoff, and the ``safety_timeout_sec``
        circuit breaker remains an absolute backstop for pathological cases.

        ``cancel_event`` is an optional per-run ``threading.Event`` created by
        the calling orchestrator. When it is set, the loop raises
        ``RunCancelledError`` immediately so the caller can close only its own
        browser context without affecting sibling concurrent runs.
        """
        # Step 0: If already cancelled, fail fast before touching the DOM.
        if cancel_event is not None and cancel_event.is_set():
            raise RunCancelledError("Cancelled before waiting for response")

        # Step 1: Check dispatch acknowledgment gate
        if not dispatch_acknowledged:
            raise RuntimeError("Cannot wait for response: prompt dispatch (EVENT_DISPATCH_ACKNOWLEDGED) is incomplete")
        _ = msg_count_before

        active_poll = PollIntervalSec(polling_interval_sec)
        active_checks = StabilityChecks(stability_checks)
        active_min_len = MinTextLength(min_text_length)

        has_thinking = False
        has_streaming = False

        # Step 2: Capture baseline message state
        log.info(
            "Waiting for AI response until terminal event (hard timeout: %ss; safety circuit breaker: %ss)",
            timeout_sec,
            self.safety_timeout_sec,
        )
        previous_text: str | None = str(baseline_text) if baseline_text is not None else _dom_latest(page)

        start = time.time()
        last_text: str | None = None
        stable_count = 0
        last_reload_time = start
        last_forward_event_time = start
        text_at_last_reload: str | None = None

        # Poll DOM for event signals and content stability until a terminal event.
        while True:
            # Step 0a: check cancellation before each poll iteration.
            if cancel_event is not None and cancel_event.is_set():
                raise RunCancelledError(f"Cancelled by user after {int(time.time() - start)}s of polling")

            now = time.time()
            elapsed = now - start
            if elapsed >= self.safety_timeout_sec:
                raise ResponseDetectionTimeoutError(
                    "Response safety circuit breaker tripped after "
                    f"{self.safety_timeout_sec}s without a terminal generation event"
                )
            # Issue #372: timeout_sec is a hard cutoff (as the MCP/CLI contracts
            # promise: "maximum seconds to wait"), raised past the safety check
            # so the absolute backstop wins when both fire on the same poll.
            if elapsed >= timeout_sec:
                raise ResponseDetectionTimeoutError(
                    f"Response hard timeout: {int(elapsed)}s elapsed exceeds the "
                    f"{timeout_sec}s cutoff without a terminal generation event"
                )

            is_thinking = self.is_thinking_active(page)
            # Reuse the thinking probe already taken this cycle: the state cannot
            # change within one iteration, so evaluating it twice only doubles
            # Chromium IPC traffic across all concurrent slots.
            is_complete = self.is_generation_complete(page, thinking=is_thinking)
            forward_event_this_iteration = False

            try:
                # Active thinking detection
                if not has_thinking and is_thinking:
                    emitter.emit(EVENT_THINKING_STARTED, {"source": "qwen-thinking-dom"})
                    has_thinking = True
                    last_forward_event_time = now
                    forward_event_this_iteration = True

                text = _dom_latest(page)
                if text is not None and should_treat_as_new_response(text, previous_text, int(active_min_len)):
                    if not has_thinking:
                        emitter.emit(EVENT_THINKING_STARTED, {"source": "response-start-fallback"})
                        has_thinking = True
                    if text == last_text:
                        stable_count += 1
                        if is_stability_satisfied(
                            stable_count, int(active_checks), has_thinking, has_streaming, is_complete
                        ):
                            # Step 4: Validate content & emit completion
                            log.info(
                                "Response stabilized after %d checks (is_complete=%s, elapsed=%ds)",
                                stable_count,
                                is_complete,
                                int(elapsed),
                            )
                            validate_response_content(text)
                            emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                            return ResponseText(text)
                    else:
                        if not has_streaming:
                            has_streaming = True
                            emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": len(text)})
                        stable_count = 0
                        last_text = text
                        last_forward_event_time = now
                        forward_event_this_iteration = True

                # Event-driven stall detection: only flag stuck when this
                # iteration produced no forward event (thinking, text
                # change, or completion). A slow-but-alive generation that
                # keeps changing text resets the stall clock each time.
                if not forward_event_this_iteration:
                    stall_elapsed = now - last_forward_event_time
                    if stall_elapsed >= self.stall_timeout_sec:
                        raise StuckDetectedError(
                            "Stuck detected: no forward lifecycle event "
                            f"(thinking/streaming/completion) for {int(stall_elapsed)}s "
                            f"(stall threshold {self.stall_timeout_sec}s)"
                        )

                # Periodic cloud sync is recovery, not a response timeout.
                # Reload only when there is no forward progress: reloading
                # mid-stream resets ``stable_count`` and can starve long
                # generations out of the stability condition (FRD FR-006,
                # issue #382). Track the committed text at last reload so a
                # steadily-growing stream suppresses the reload even across
                # the 30-second window.
                if (now - last_reload_time) >= 30.0 and last_text == text_at_last_reload:
                    log.info(
                        "Periodic 30s cloud reload sync: refreshing page to pull Qwen Cloud state (elapsed: %ds)...",
                        int(elapsed),
                    )
                    last_reload_time = now
                    with contextlib.suppress(Exception):
                        page.reload(wait_until="domcontentloaded", timeout=15_000)
                        page.wait_for_timeout(2000)
                        text_at_last_reload = last_text
                        continue

                time.sleep(active_poll)
            except TimeoutError as e:
                log.warning("Browser operation timed out while waiting; keeping event-driven monitor alive: %s", e)
                last_reload_time = time.time()
                continue
            except Error as e:
                log.warning(
                    "Browser error or connection reset during polling (%s). Attempting page reload recovery...", e
                )
                last_reload_time = time.time()
                with contextlib.suppress(Exception):
                    page.reload(wait_until="domcontentloaded", timeout=15_000)
                    page.wait_for_timeout(2000)
                    continue
            except (AuthRequiredError, OutputValidationError):
                raise
            except Exception as e:
                log.error("Unexpected error during polling: %s", e)
                raise

    def __repr__(self) -> str:
        """Return string representation of StreamMonitor."""
        return (
            f"StreamMonitor(poll={self.polling_interval_sec}, checks={self.stability_checks}, "
            f"min_len={self.min_text_length})"
        )
