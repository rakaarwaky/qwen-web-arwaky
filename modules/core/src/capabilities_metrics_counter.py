"""Capability layer (capabilities_metrics_counter): thread-safe metrics collector.

Implements IMetricsProtocol.
Thread-safe JSON-backed metrics persistence with rolling 24h execution events.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.shared.src.contract_core_protocol import IMetricsProtocol
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG
from modules.shared.src.taxonomy_core_vo import MessageCount
from modules.shared.src.utility_io_writer import atomic_write_json
from modules.shared.src.utility_telemetry_scrubber import harden_private_file


class MetricsCounter(IMetricsProtocol):
    """Thread-safe metrics collector persisted in a rolling-window JSON file."""

    def __init__(self, metrics_path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._metrics_path = Path(metrics_path or (DEFAULT_LOG / "metrics.json"))
        self._counters: dict[str, int] = {}
        self._execution_events: list[dict[str, Any]] = []
        self._start_time = datetime.now(tz=timezone.utc)
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self._metrics_path.read_text(encoding="utf-8"))
            counters = raw.get("counters", {}) if isinstance(raw, dict) else {}
            if isinstance(counters, dict):
                self._counters = {str(k): int(v) for k, v in counters.items()}
            events = raw.get("execution_events", []) if isinstance(raw, dict) else []
            if isinstance(events, list):
                self._execution_events = [event for event in events if isinstance(event, dict)]
            self._prune_events()
        except (OSError, ValueError, TypeError):
            self._counters = {}
            self._execution_events = []

    def _prune_events(self) -> None:
        cutoff = datetime.now(tz=timezone.utc).timestamp() - 24 * 60 * 60
        kept: list[dict[str, Any]] = []
        for event in self._execution_events:
            try:
                if datetime.fromisoformat(str(event["at"]).replace("Z", "+00:00")).timestamp() >= cutoff:
                    kept.append(event)
            except (KeyError, TypeError, ValueError):
                continue
        self._execution_events = kept

    def _persist(self) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self._prune_events()
        total = len(self._execution_events)
        successful = sum(1 for event in self._execution_events if event.get("success") is True)
        atomic_write_json(
            self._metrics_path,
            {
                "window": "rolling_24h",
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
                "counters": self._counters,
                "execution_events": self._execution_events,
                "total_executions": total,
                "successful_executions": successful,
            },
        )
        # Counters describe failure rates, which is telemetry an operator may
        # not want world-readable, so the file is owner-only regardless of the
        # process umask (issue #352).
        harden_private_file(self._metrics_path)

    def increment(self, key: str, amount: MessageCount = MessageCount(1)) -> None:
        """Add *amount* to the counter *key* and persist the metrics file."""
        with self._lock:
            self._counters[key] = self._counters.get(key, MessageCount(0)) + amount
            self._persist()

    def record_execution(self, success: bool) -> None:
        """Record one terminal pipeline execution for the reliability SLO."""
        with self._lock:
            self._execution_events.append({"at": datetime.now(tz=timezone.utc).isoformat(), "success": bool(success)})
            self._persist()

    def record_failure(self, category: str) -> None:
        """Bump one occurrence for *category* in the rolling error counter.

        Unknown category names are ignored so a caller passing a raw exception
        type name cannot inflate the defect counts with unbounded keys; the
        taxonomy is the single source of truth for valid buckets.  Failures are
        stored under an ``error.`` prefix so they cannot collide with the plain
        counter names that pipeline stages use (``files_processed`` and friends).
        """
        from modules.shared.src.taxonomy_core_error import ErrorCategory

        if category not in ErrorCategory.known():
            return
        with self._lock:
            self._counters[f"error.{category}"] = self._counters.get(f"error.{category}", 0) + 1
            self._persist()

    def failure_counts(self) -> dict[str, int]:
        """Return the rolling per-category error counts, ranked by descending count.

        Keys are ``ErrorCategory`` names with the ``error.`` counter prefix
        stripped, so a defect-density report can read them directly.
        """
        with self._lock:
            prefix = "error."
            counts = {key[len(prefix) :]: value for key, value in self._counters.items() if key.startswith(prefix)}
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def get(self, key: str) -> MessageCount:
        """Return the current value of counter *key* (0 when absent)."""
        with self._lock:
            return MessageCount(self._counters.get(key, 0))

    def snapshot(self) -> dict[str, Any]:
        """Return all counters plus rolling-24h execution totals and success rate."""
        with self._lock:
            self._prune_events()
            result: dict[str, Any] = dict(self._counters)
            total = len(self._execution_events)
            successful = sum(1 for event in self._execution_events if event.get("success") is True)
            result["total_executions"] = total
            result["successful_executions"] = successful
            result["success_rate"] = round(successful / total, 6) if total else None
            return result

    def __repr__(self) -> str:
        return f"MetricsCounter(path={self._metrics_path!s})"


__all__ = ["MetricsCounter"]
