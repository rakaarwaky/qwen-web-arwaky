"""Regression tests: structlog loggers must not emit %-format event strings.

Defect being locked down:
    ``capabilities_browser_adapter.py`` used ``log = structlog.get_logger("browser")``
    but called it with stdlib ``%-style`` positional args, e.g.::

        log.warning("Load state wait failed, proceeding: %s", err)

    Through the structlog stdlib bridge + ``ProcessorFormatter(JSONRenderer)``,
    that produced ``{"event": "Load state wait failed, proceeding: %s",
    "positional_args": ["TimeoutError(...)"]}`` — the human-readable ``event``
    kept the literal ``%s`` and the real value leaked into a ``positional_args``
    key that no consumer (JSONL reader, TUI RichLog, monitoring) interpolates.
    Every emitted record was thus missing its actual error value.

    The fix converts those calls to structlog keyword-arg style, e.g.::

        log.warning("load_state_wait_failed_proceeding", err=str(err))

    These tests pin that contract.
"""

from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from typing import Any

import structlog
import structlog.processors as p
import structlog.stdlib as s


def _make_jsonl_sink() -> tuple[s.ProcessorFormatter, logging.Handler, io.StringIO]:
    """Build a ProcessorFormatter + file handler that writes one JSON line per record.

    Mirrors the production ``capabilities_observability_setup`` wiring closely
    enough to reproduce the defect: a structlog logger wrapped into stdlib via
    ``LoggerFactory`` + ``wrap_for_formatter``, then formatted by a
    ``ProcessorFormatter`` with a JSON renderer and a real logging handler.
    """
    shared_processors: list[Any] = [
        s.add_log_level,
        p.TimeStamper(fmt="iso", utc=True),
        p.StackInfoRenderer(),
        p.format_exc_info,
    ]
    renderer = p.JSONRenderer(ensure_ascii=False)

    structlog.configure(
        processors=shared_processors + [s.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=s.BoundLogger,
        logger_factory=s.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    formatter = s.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[s.ProcessorFormatter.remove_processors_meta, renderer],
    )
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return formatter, handler, buf


def _clean_emit_and_read(event: str, **kw: Any) -> dict[str, Any]:
    """Emit one structlog record into a fresh JSONL sink and return the parsed record."""
    _, _, buf = _make_jsonl_sink()
    structlog.get_logger("regression_probe").warning(event, **kw)
    buf.seek(0)
    return json.loads(buf.readline())


def test_structlog_kwarg_call_produces_clean_event() -> None:
    """A keyword-arg structlog call must render a clean event with no %-placeholder."""
    record = _clean_emit_and_read("some_event", detail="value")
    assert record["event"] == "some_event"
    assert record["detail"] == "value"
    assert record["level"] == "warning"
    assert "%" not in record["event"]


def test_old_percent_style_leaks_positional_args() -> None:
    """Document the old broken style: event keeps its %-placeholder, value leaks to positional_args."""
    _, _, buf = _make_jsonl_sink()
    structlog.get_logger("regression_probe").warning("Load state wait failed, proceeding: %s", "TimeoutError('x')")
    buf.seek(0)
    record = json.loads(buf.readline())
    # The defect signature: literal %-placeholder in event + stashed positional_args.
    assert "%s" in record["event"]
    assert "positional_args" in record

    # The fixed keyword style is clean.
    fixed = _clean_emit_and_read("load_state_wait_failed_proceeding", err="TimeoutError('x')")
    assert fixed["event"] == "load_state_wait_failed_proceeding"
    assert fixed["err"] == "TimeoutError('x')"
    assert "%" not in fixed["event"]
    assert "positional_args" not in fixed


_PERCENT_IN_LOG_CALL_RE = re.compile(r"""log\.(?:debug|info|warning|error|critical|exception)\(\s*["'].*?%[a-zA-Z]""")


def test_browser_adapter_has_no_percent_style_structlog_calls() -> None:
    """Static guard: capabilities_browser_adapter.py has no %-style log calls.

    Locks the source so a future edit cannot reintroduce the defect.
    """
    src = Path(__file__).resolve().parents[1] / "src" / "capabilities_browser_adapter.py"
    text = src.read_text(encoding="utf-8")
    offenders = [m.group(0) for m in _PERCENT_IN_LOG_CALL_RE.finditer(text)]
    assert not offenders, "%-style structlog log calls reintroduced in browser_adapter:\n" + "\n".join(offenders)


def test_browser_adapter_module_logger_emits_no_positional_args() -> None:
    """End-to-end: the real browser-adapter module logger, used keyword-style, is clean."""
    from modules.core.src import capabilities_browser_adapter as adapter

    assert adapter.log is not None
    record = _clean_emit_and_read("load_state_wait_failed_proceeding", err="TimeoutError('15000ms exceeded')")
    assert record["event"] == "load_state_wait_failed_proceeding"
    assert record["err"] == "TimeoutError('15000ms exceeded')"
    assert "%" not in record["event"]
    assert "positional_args" not in record
