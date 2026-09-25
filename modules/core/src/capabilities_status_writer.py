"""Capability layer (capabilities_status_writer): status file write/read.

Implements IStatusProtocol.
Atomic JSON status file for systemd / monitoring tools.
"""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.core.src.utility_core_io_writer import atomic_write_json, ensure_dir
from modules.shared.src.contract_core_protocol import IStatusProtocol
from modules.shared.src.taxonomy_core_vo import StatusRecordVO
from modules.shared.src.utility_core_status import status_path_for

#: Version of the ``status.json`` document contract. Bumped when a field is
#: added or its meaning changes, so external monitors can branch on it
#: (issue #296).
STATUS_SCHEMA_VERSION = 2


class StatusFileWriter(IStatusProtocol):
    """Atomic JSON status file for systemd / monitoring tools."""

    def __init__(self, status_path: Path) -> None:
        self._status_path = status_path
        ensure_dir(self._status_path)

    def write(self, **kwargs: Any) -> None:
        """Atomically write the status JSON from keyword fields.

        When a ``metrics`` mapping is supplied it is embedded under
        ``metrics``, so an external monitor reading ``status.json`` sees the
        same counters the process keeps alive in memory (issue #296). The
        document is also stamped with ``schema_version`` and ``updated_at``
        so a monitor can parse it without guessing. Field contract:

        - ``schema_version``: int, currently 2.
        - ``updated_at``: ISO-8601 UTC timestamp of the write.
        - ``status`` / ``mode`` / ``headless`` / ``run_id``: run identity.
        - ``files_processed`` / ``files_failed`` / ``cpu_sec``: run totals.
        - ``failure_categories``: optional mapping of
          :class:`~modules.shared.src.taxonomy_core_error.ErrorCategory` values
          to occurrence counts, letting monitoring tools answer "which
          capability is most defective?" without parsing ``app.jsonl`` by hand.
        - ``metrics``: counters plus ``total_executions``,
          ``successful_executions``, and ``success_rate`` over a rolling 24 h
          window (``None`` when no execution has been recorded).
        - ``error``: present only when the run failed.
        """
        rec: dict[str, Any] = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            "status": kwargs.get("status", "unknown"),
            "mode": kwargs.get("mode", "unknown"),
            "headless": kwargs.get("headless", False),
            "run_id": kwargs.get("run_id"),
            "files_processed": kwargs.get("files_processed", 0),
            "files_failed": kwargs.get("files_failed", 0),
            "failure_categories": normalise_categories(kwargs.get("failure_categories")),
        }
        metrics = kwargs.get("metrics")
        if isinstance(metrics, dict):
            rec["metrics"] = metrics
        if kwargs.get("cpu_sec") is not None:
            rec["cpu_sec"] = round(kwargs["cpu_sec"], 2)
        if kwargs.get("error"):
            rec["error"] = kwargs["error"]

        with suppress(OSError):
            atomic_write_json(self._status_path, rec)

    def write_record(self, record: StatusRecordVO, *, metrics: dict[str, Any] | None = None) -> None:
        """Write the status JSON from a typed status record.

        ``metrics`` carries the persisted counter snapshot so a monitor reading
        only ``status.json`` still sees the rolling-24h execution totals
        (issue #296).
        """
        self.write(
            status=record.status,
            mode=record.mode,
            headless=record.headless,
            run_id=record.run_id,
            error=record.error,
            cpu_sec=record.cpu_sec,
            files_processed=record.files_processed,
            files_failed=record.files_failed,
            metrics=metrics,
        )

    def read(self) -> dict[str, Any] | None:
        """Return the parsed status file, or None when missing or invalid."""
        try:
            result: Any = json.loads(self._status_path.read_text(encoding="utf-8"))
            return result if isinstance(result, dict) else None
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return None

    def __repr__(self) -> str:
        return "StatusFileWriter()"

    @classmethod
    def create_default(cls, log_path: Path) -> StatusFileWriter:
        """Build a writer targeting the conventional status path for *log_path*."""
        return cls(status_path_for(log_path))


def get_status_writer(log_path: Path) -> StatusFileWriter:
    """Create a status writer at log_path/status.json."""
    return StatusFileWriter.create_default(log_path)


def normalise_categories(raw: Any) -> dict[str, int]:
    """Coerce a failure-category breakdown into a sorted ``{category: count}`` map.

    Accepts ``None``, a mapping, or an iterable of pairs.  Non-integer counts
    are dropped rather than written as strings, so ``status.json`` keeps a
    stable schema that monitoring tools can sum without type coercion.
    """
    if not raw:
        return {}
    items = raw.items() if isinstance(raw, dict) else raw
    result: dict[str, int] = {}
    for pair in items:
        try:
            key, value = pair
            result[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return dict(sorted(result.items(), key=lambda kv: (-kv[1], kv[0])))


__all__ = ["StatusFileWriter", "get_status_writer"]
