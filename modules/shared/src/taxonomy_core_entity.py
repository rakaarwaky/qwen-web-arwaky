"""Stateful domain entities: circuit breaker, rate limiter, lifecycle emitter.

Taxonomy layer (taxonomy(entity)): identity-bearing stateful entities, no I/O.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
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
from modules.shared.src.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec

log = logging.getLogger(__name__)


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
        self._trip = len(self._failures) >= self._threshold

    def record_success(self) -> None:
        """Reset the breaker on a successful request."""
        with self._lock:
            self._failures.clear()
            self._trip = False

    def record_failure(self) -> None:
        """Record a failure and trip if threshold exceeded within window."""
        with self._lock:
            self._failures.append(time.time())
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

    def _try_reserve_locked(self, now: float) -> float | None:
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
        return max(0.1, 60.0 - (now - oldest) + 0.1)

    def try_acquire(self) -> float | None:
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
        self._predecessor = {event: ordered[index - 1] for index, event in enumerate(ordered) if index > 0}

    @property
    def completed(self) -> tuple[QwenEventType, ...]:
        """Return the accepted event sequence in emission order."""
        return tuple(self._completed)

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

    @property
    def completed(self) -> tuple[QwenEventType, ...]:
        """Return accepted events from the attached lifecycle gate."""
        return self._gate.completed if self._gate is not None else ()

    def on(self, event_name: QwenEventType | str, callback: LifecycleCallback) -> None:
        """Register a callback for a named lifecycle event."""
        key = str(event_name)
        self._callbacks.setdefault(key, []).append(callback)

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
                self._log(EventMessage(f"lifecycle_callback_error event={key} error={exc}"))
        return evt

    def _log(self, message: EventMessage) -> None:
        """Log a message via the injected logger (callable or .info())."""
        if callable(self._logger):
            self._logger(message)
        else:
            self._logger.info(message)
