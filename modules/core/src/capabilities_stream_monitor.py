"""Capabilities: stream monitor (AES403).

Implements IStreamProtocol.
"""

from __future__ import annotations

import contextlib
import time

from playwright.sync_api import Error, Page

from modules.core.src.utility_core_dom_helper import is_any_visible
from modules.core.src.utility_core_dom_query import latest_message_text as _dom_latest
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
DEFAULT_SAFETY_TIMEOUT_SEC = 4 * 60 * 60


# Block 1: Class Definition & Constructor


class StreamMonitor(IStreamProtocol):
    """Response streaming detection and stability polling."""

    def __init__(
        self,
        config: StreamerConfig | None = None,
        *,
        safety_timeout_sec: int = DEFAULT_SAFETY_TIMEOUT_SEC,
    ) -> None:
        if safety_timeout_sec <= 0:
            raise ValueError("safety_timeout_sec must be greater than zero")
        self.safety_timeout_sec = int(safety_timeout_sec)
        if config is not None:
            self.polling_interval_sec = PollIntervalSec(config.polling_interval_sec)
            self.stability_checks = StabilityChecks(config.stability_checks)
            self.min_text_length = MinTextLength(config.min_text_length)
        else:
            self.polling_interval_sec = PollIntervalSec(1.0)
            self.stability_checks = StabilityChecks(4)
            self.min_text_length = MinTextLength(1)

    # ─── Block 2: Public Contract (IStreamProtocol ONLY) ──
    def is_generation_complete(self, page: Page) -> bool:
        """Check if Qwen AI is done generating."""
        try:
            if is_any_visible(page, STOP_BUTTON_SELECTORS):
                return False
            return not self.is_thinking_active(page)
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
    ) -> ResponseText | None:
        """Wait for a terminal assistant response using event-driven DOM signals.

        ``timeout_sec`` is retained for API compatibility and observability only;
        it is not a response cutoff. The loop exits on a terminal generation event
        (stable response plus a completed generation state), or raises when an
        explicit browser/auth error cannot be recovered.
        """
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
            "Waiting for AI response until terminal event (timeout hint: %ss; safety circuit breaker: %ss)",
            timeout_sec,
            self.safety_timeout_sec,
        )
        previous_text: str | None = str(baseline_text) if baseline_text is not None else _dom_latest(page)

        start = time.time()
        last_text: str | None = None
        stable_count = 0
        last_reload_time = start

        # Poll DOM for event signals and content stability until a terminal event.
        while True:
            now = time.time()
            elapsed = now - start
            if elapsed >= self.safety_timeout_sec:
                raise ResponseDetectionTimeoutError(
                    "Response safety circuit breaker tripped after "
                    f"{self.safety_timeout_sec}s without a terminal generation event"
                )

            is_thinking = self.is_thinking_active(page)
            is_complete = self.is_generation_complete(page)

            try:
                # Active thinking detection
                if not has_thinking and is_thinking:
                    emitter.emit(EVENT_THINKING_STARTED, {"source": "qwen-thinking-dom"})
                    has_thinking = True

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

                # Periodic cloud sync is recovery, not a response timeout. It runs
                # while waiting so a long-running Qwen generation can continue past
                # any configured hint without being cut off.
                if (now - last_reload_time) >= 30.0:
                    log.info(
                        "Periodic 30s cloud reload sync: refreshing page to pull Qwen Cloud state (elapsed: %ds)...",
                        int(elapsed),
                    )
                    last_reload_time = now
                    with contextlib.suppress(Exception):
                        page.reload(wait_until="domcontentloaded", timeout=15_000)
                        page.wait_for_timeout(2000)
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
