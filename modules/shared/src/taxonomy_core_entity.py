"""Stateful domain entities: circuit breaker, rate limiter, lifecycle emitter.

Taxonomy layer (taxonomy(entity)): identity-bearing stateful entities, no I/O.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter, deque
from collections.abc import Callable, Sequence
from typing import Protocol

from modules.shared.src.taxonomy_core_constant import MAX_ATTEMPTS
from modules.shared.src.taxonomy_core_event import (
    EVENT_DESCRIPTIONS,
    PIPELINE_EVENT_SEQUENCE,
    CallbackRegistry,
    EventDetails,
    EventMessage,
    LifecycleCallback,
    LifecycleEvent,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import (
    EventSequenceVO,
    EventTimestamp,
    FailureCategory,
    FailureCategoryCounts,
    FailureThreshold,
    MaxPerMinute,
    RetryWaitSec,
    WindowSec,
)

log = logging.getLogger(__name__)


def _count_categories(categories: Sequence[FailureCategory]) -> FailureCategoryCounts:
    """Tally *categories* into counts, ranked by descending count.

    Taxonomy owns the ranking rule so ``trip_category`` and
    ``failure_categories`` cannot disagree on ordering.
    """
    tally = Counter(categories)
    return FailureCategoryCounts(dict(sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))))


class CircuitBreaker:
    """Sliding-window circuit breaker for request-level failure tracking."""

    def __init__(
        self,
        threshold: FailureThreshold = FailureThreshold(MAX_ATTEMPTS),
        window_sec: WindowSec = WindowSec(30),
    ) -> None:
        """Initialize circuit breaker with sliding-window failure threshold.

        Args:
            threshold: Number of failures within window_sec to trip the breaker.
            window_sec: Sliding time window in seconds for counting failures.

        Raises:
            ValueError: If threshold or window_sec < 1.

        """
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")
        if window_sec < 1:
            raise ValueError(f"window_sec must be >= 1, got {window_sec}")
        self._threshold = threshold
        self._window_sec = window_sec
        self._failures: deque[float] = deque()
        self._failure_categories: deque[FailureCategory] = deque()
        self._trip: bool = False
        # Job workers call record_failure/record_success from up to
        # DEFAULT_MAX_WORKERS threads; every mutation must be serialized so the
        # prune-then-count sequence in _refresh_state stays atomic.
        self._lock = threading.Lock()

    def configure(self, threshold: FailureThreshold, window_sec: WindowSec) -> None:
        """Update limits while preserving accumulated failure history."""
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")
        if window_sec < 1:
            raise ValueError(f"window_sec must be >= 1, got {window_sec}")
        with self._lock:
            self._threshold = threshold
            self._window_sec = window_sec
            self._refresh_state()

    def _refresh_state(self) -> None:
        """Discard expired failures and recompute the trip state.

        Callers must already hold ``self._lock``.
        """
        current = time.time()
        while self._failures and (current - self._failures[0]) > self._window_sec:
            self._failures.popleft()
            if self._failure_categories:
                self._failure_categories.popleft()
        self._trip = len(self._failures) >= self._threshold

    def record_success(self) -> None:
        """Reset the breaker on a successful request."""
        with self._lock:
            self._failures.clear()
            self._failure_categories.clear()
            self._trip = False

    def record_failure(self, category: FailureCategory | None = None) -> None:
        """Record a failure and trip if threshold exceeded within window.

        ``category`` is the :class:`~modules.shared.src.taxonomy_core_error.
        ErrorCategory` of the triggering failure.  When a single category is
        responsible for most of the window's failures, the trip exposes it so
        "why did the breaker open?" has one-line answers without log mining.
        """
        with self._lock:
            self._failures.append(time.time())
            if category:
                self._failure_categories.append(category)
            self._refresh_state()

    @property
    def threshold(self) -> int:
        """Configured consecutive-failure threshold."""
        return int(self._threshold)

    @property
    def window_sec(self) -> int:
        """Configured failure observation window in seconds."""
        return int(self._window_sec)

    @property
    def is_tripped(self) -> bool:
        """True when the breaker has tripped."""
        with self._lock:
            self._refresh_state()
            return self._trip

    @property
    def trip_category(self) -> FailureCategory | None:
        """ErrorCategory of the failure that tripped the breaker, when known.

        Returns the single dominant category when one accounts for a strict
        majority of the in-window failures, and ``None`` when the failures are
        mixed or were recorded without a category. A mixed window has no single
        cause, so no single answer is reported.
        """
        with self._lock:
            self._refresh_state()
            if not self._trip or not self._failure_categories:
                return None
            counts = _count_categories(self._failure_categories)
            top, top_count = next(iter(counts.items()))
            return FailureCategory(top) if top_count * 2 > len(self._failure_categories) else None

    @property
    def failure_categories(self) -> FailureCategoryCounts:
        """In-window failure counts per category, for defect-density reporting."""
        with self._lock:
            self._refresh_state()
            return _count_categories(self._failure_categories)


class RateLimiter:
    """Simple token-bucket rate limiter for request throttling."""

    def __init__(self, max_per_minute: MaxPerMinute = MaxPerMinute(60)) -> None:
        """Initialize rate limiter with a fixed window of max requests per minute.

        Args:
            max_per_minute: Maximum number of acquire() calls allowed per 60-second window.

        Raises:
            ValueError: If max_per_minute < 1.

        """
        if max_per_minute < MaxPerMinute(1):
            raise ValueError(f"max_per_minute must be >= 1, got {max_per_minute}")
        self._max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()
        # Dispatch guards may run concurrently (MCP executes submits on an
        # executor); the prune/count/append sequence must not interleave.
        self._lock = threading.Lock()

    def configure(self, max_per_minute: MaxPerMinute) -> None:
        """Update the request limit while preserving timestamp history."""
        if max_per_minute < MaxPerMinute(1):
            raise ValueError(f"max_per_minute must be >= 1, got {max_per_minute}")
        with self._lock:
            self._max_per_minute = max_per_minute

    @property
    def max_per_minute(self) -> int:
        """Configured maximum requests per minute."""
        return int(self._max_per_minute)

    def _try_reserve_locked(self, now: EventTimestamp) -> RetryWaitSec | None:
        """Reserve a slot if available; else return seconds until one frees.

        Callers must already hold ``self._lock``.
        """
        window_start = now - 60.0
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()
        if len(self._timestamps) < self._max_per_minute:
            self._timestamps.append(now)
            return None
        oldest = self._timestamps[0]
        return RetryWaitSec(max(0.1, 60.0 - (now - oldest) + 0.1))

    def try_acquire(self) -> RetryWaitSec | None:
        """Reserve a slot without blocking.

        Returns:
            ``None`` when a slot was reserved, otherwise the number of seconds
            the caller should wait before retrying.

        """
        with self._lock:
            return self._try_reserve_locked(time.time())

    def acquire(self) -> None:
        """Wait until a request slot is available."""
        while True:
            with self._lock:
                wait_sec = self._try_reserve_locked(time.time())
            if wait_sec is None:
                return
            time.sleep(wait_sec)


class LifecycleState:
    """Mutable run-local gates driven only by emitted lifecycle events."""

    def __init__(self) -> None:
        self.web_loaded = False
        self.login_verified = False
        self.file_uploaded = False
        self.prompt_injected = False
        self.document_parsed = False
        self.send_clicked = False
        self.dispatch_acknowledged = False
        self.thinking_started = False
        self.streaming_generation = False
        self.generation_finished = False
        self.output_copied = False

    def mark(self, event_name: QwenEventType | str) -> None:
        """Advance exactly the gate represented by an emitted event."""
        key = str(event_name)
        flags = {
            str(QwenEventType.WEB_LOADED): "web_loaded",
            str(QwenEventType.LOGIN_VERIFIED): "login_verified",
            str(QwenEventType.FILE_UPLOADED): "file_uploaded",
            str(QwenEventType.PROMPT_INJECTED): "prompt_injected",
            str(QwenEventType.DOCUMENT_PARSED): "document_parsed",
            str(QwenEventType.SEND_CLICKED): "send_clicked",
            str(QwenEventType.DISPATCH_ACKNOWLEDGED): "dispatch_acknowledged",
            str(QwenEventType.THINKING_STARTED): "thinking_started",
            str(QwenEventType.STREAMING_GENERATION): "streaming_generation",
            str(QwenEventType.GENERATION_FINISHED): "generation_finished",
            str(QwenEventType.OUTPUT_COPIED): "output_copied",
        }
        if key in flags:
            setattr(self, flags[key], True)


class LifecycleLogger(Protocol):
    """Logger protocol accepted by lifecycle entities."""

    def info(self, message: EventMessage) -> object:
        """Record an informational lifecycle message."""


class LifecycleGate:
    """Strict predecessor gate for the ordered processing lifecycle.

    The accepted event order is supplied per run via ``sequence`` (defaulting to
    the global ``PIPELINE_EVENT_SEQUENCE``). This lets each pipeline declare the
    exact events it will emit — e.g. a no-attachment run omits
    ``DOCUMENT_PARSED`` so the gate no longer requires it — while still enforcing
    that ``EVENT_LOGIN_VERIFIED`` precedes every other execution event.
    """

    def __init__(
        self,
        logger: Callable[..., object] | LifecycleLogger | None = None,
        sequence: Sequence[QwenEventType] | None = None,
    ) -> None:
        self._logger = logger
        self._completed: list[QwenEventType] = []
        self.rejections: list[dict[str, str]] = []
        ordered = sequence if sequence is not None else PIPELINE_EVENT_SEQUENCE
        self._sequence: EventSequenceVO = EventSequenceVO(ordered)
        self._predecessor = {event: ordered[index - 1] for index, event in enumerate(ordered) if index > 0}

    @property
    def sequence(self) -> EventSequenceVO:
        """Return the configured event sequence this gate validates against."""
        return self._sequence

    @property
    def completed(self) -> EventSequenceVO:
        """Return the accepted event sequence in emission order."""
        return EventSequenceVO(self._completed)

    def validate(self, event_name: QwenEventType | str) -> None:
        """Accept an event or raise with an auditable predecessor reason."""
        try:
            event = event_name if isinstance(event_name, QwenEventType) else QwenEventType(str(event_name))
        except ValueError:
            log.warning("lifecycle_gate_rejected_unknown_event event=%r", event_name)
            return

        predecessor = self._predecessor.get(event)
        if event in self._completed:
            reason = f"{event} was already emitted"
        elif predecessor is not None and (not self._completed or self._completed[-1] != predecessor):
            last_event = self._completed[-1] if self._completed else "none"
            reason = f"requires successful predecessor {predecessor}; last event was {last_event}"
        else:
            self._completed.append(event)
            return

        rejection = {"event": event.value, "reason": reason}
        self.rejections.append(rejection)
        self._log(EventMessage(f"lifecycle_gate_rejected event={event} reason={reason}"))
        raise RuntimeError(f"Lifecycle gate rejected {event}: {reason}")

    def reset(self, completed_prefix: EventSequenceVO | None = None) -> None:
        """Roll back run-local progress so a dispatch retry can re-emit the
        per-attempt events (prompt-injected onward) without tripping the
        "already emitted" rejection.

        Page-phase events are re-seeded from ``completed_prefix`` (an
        accepted prefix of the configured sequence) because the page is
        reused across attempts: the browser adapter does not re-emit
        WEB_LOADED / LOGIN_VERIFIED / MODEL_VERIFIED, and neither does the
        attachment pipeline re-emit FILE_UPLOADED / DOCUMENT_PARSED.
        """
        prefix = completed_prefix if completed_prefix is not None else ()
        self._completed.clear()
        self.rejections.clear()
        for event in prefix:
            typed_event = QwenEventType(event)
            self._validate_prefix_event(typed_event)
            self._completed.append(typed_event)

    def _validate_prefix_event(self, event: QwenEventType) -> None:
        """Accept a re-seeded prefix event or reject an invalid reset seed."""
        predecessor = self._predecessor.get(event)
        if predecessor is None or (self._completed and self._completed[-1] == predecessor):
            return
        raise ValueError(
            f"Lifecycle gate reset prefix is invalid: {event} requires predecessor "
            f"{predecessor}, but the last re-seeded event was "
            f"{self._completed[-1] if self._completed else 'none'}"
        )

    def _log(self, message: EventMessage) -> None:
        if self._logger is None:
            return
        if callable(self._logger):
            self._logger(message)
        else:
            self._logger.info(message)


class LifecycleEmitter:
    """Event bus for pipeline lifecycle events with typed dispatcher capability."""

    def __init__(
        self,
        logger: Callable[..., object] | LifecycleLogger | None = None,
        gate: LifecycleGate | None = None,
    ) -> None:
        """Initialize callbacks, an optional logger, and an optional strict gate."""
        self._callbacks: CallbackRegistry = {}
        self._logger = logger or logging.getLogger("lifecycle")
        self._gate = gate
        self.callback_errors: list[dict[str, str]] = []

    @property
    def gate(self) -> LifecycleGate | None:
        """Return the attached lifecycle gate, or None when ungated."""
        return self._gate

    @property
    def completed(self) -> EventSequenceVO:
        """Return accepted events from the attached lifecycle gate."""
        if self._gate is not None:
            return self._gate.completed
        return EventSequenceVO(())

    @property
    def sequence(self) -> EventSequenceVO:
        """Return the configured event sequence this gate validates against."""
        if self._gate is not None:
            return self._gate.sequence
        return EventSequenceVO(())

    def on(self, event_name: QwenEventType | str, callback: LifecycleCallback) -> None:
        """Register a callback for a named lifecycle event."""
        key = str(event_name)
        self._callbacks.setdefault(key, []).append(callback)

    def observe(self, observer: Callable[[QwenEventType, LifecycleEvent], None]) -> None:
        """Register a listener for every pipeline event emitted on this bus.

        Surfaces use this to render event-level status (thinking,
        streaming, prompting) instead of only IDLE/RUNNING. The observer
        receives the ``QwenEventType`` and the structured ``LifecycleEvent``.
        """

        def _dispatch(event: LifecycleEvent) -> None:
            try:
                enum_member = QwenEventType(str(event.name))
            except ValueError:
                return
            observer(enum_member, event)

        for event_name in QwenEventType:
            self.on(event_name, _dispatch)

    def emit(self, event_name: QwenEventType | str, details: EventDetails | None = None) -> LifecycleEvent:
        """Emit a lifecycle event to all registered callbacks."""
        key = str(event_name)
        if self._gate is not None:
            self._gate.validate(event_name)
        evt = LifecycleEvent(
            name=key,
            timestamp=time.time(),
            details=details or {},
        )
        enum_member = event_name if isinstance(event_name, QwenEventType) else None
        label = EVENT_DESCRIPTIONS.get(enum_member, key) if enum_member else key
        detail_str = f" - {details}" if details else ""
        self._log(EventMessage(f"[{key}] {label}{detail_str}"))
        for cb in self._callbacks.get(key, []):
            try:
                cb(evt)
            except Exception as exc:  # third-party callbacks may raise anything; must not break emission
                err_dict = {
                    "event": key,
                    "error": f"{exc}",
                    "type": f"{type(exc).__name__}",
                }
                self.callback_errors.append(err_dict)
                if hasattr(self._logger, "error") and callable(self._logger.error):
                    self._logger.error("lifecycle_callback_error event=%s error=%s", key, exc, exc_info=True)
                else:
                    self._log(EventMessage(f"lifecycle_callback_error event={key} error={exc}"))
        return evt

    def _log(self, message: EventMessage) -> None:
        """Log a message via the injected logger (callable or .info())."""
        if callable(self._logger):
            self._logger(message)
        else:
            self._logger.info(message)
