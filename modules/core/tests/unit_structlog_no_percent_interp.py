"""Regression tests: capabilities_browser_adapter uses stdlib printf-style logging.

Defect being locked down (issue #366):
    ``capabilities_browser_adapter.py`` used ``structlog.get_logger`` but called
    it with keyword arguments that structlog treats as extra fields — the
    event name was always a bare message string, so passing ``key=value``
    instead of ``%s`` args would leak no value into the ``event`` field. When
    we later moved the logger to stdlib via ``get_logger``, passing
    keyword args instead of positional printf args would raise
    ``TypeError: Logger._log() got an unexpected keyword argument``.

    The fix converts those calls to stdlib printf-style, e.g.::

        log.warning("load_state_wait_failed_proceeding %s", str(err))

    These tests pin that contract so a future edit cannot regress to
    either keyword-arg structlog calls or bare %-placeholders without args.
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


def test_browser_adapter_has_no_kwarg_style_log_calls() -> None:
    """Static guard: capabilities_browser_adapter.py has no keyword-arg log calls.

    Locks the source so a future edit cannot reintroduce the TypeError from
    passing ``key=value`` to a stdlib logger.
    """
    src = Path(__file__).resolve().parents[2] / "browser" / "src" / "capabilities_browser_adapter.py"
    text = src.read_text(encoding="utf-8")
    kwarg_re = re.compile(r"""log\.(?:debug|info|warning|error|critical|exception)\([^)]*?\w+=[\w.]""")
    offenders = [m.group(0) for m in kwarg_re.finditer(text)]
    assert not offenders, "keyword-arg log calls reintroduced in browser_adapter:\n" + "\n".join(offenders)


def test_browser_adapter_module_logger_is_stdlib() -> None:
    """End-to-end: the real browser-adapter module logger is a stdlib logger, not structlog."""
    import logging as _logging

    from modules.browser.src import capabilities_browser_adapter as adapter

    assert isinstance(adapter.log, _logging.Logger), (
        f"browser adapter logger must be a stdlib logging.Logger, got {type(adapter.log).__name__}"
    )
    assert adapter.log.name == "browser"
