"""Shared test helpers: standalone wrappers duplicated across test files.

These thin delegates exist only to give each wrapper its own name for pytest
output — the underlying class/function is what actually matters.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_observability_setup import (
    ObservabilitySetup,
)
from modules.core.src.capabilities_observability_setup import (
    _bind_run_context as _obs_bind,
)
from modules.core.src.capabilities_observability_setup import (
    _clear_run_context as _obs_clear,
)
from modules.core.src.capabilities_observability_setup import (
    _get_logger as _obs_get_logger,
)
from modules.core.src.capabilities_observability_setup import (
    _get_tracer as _obs_get_tracer,
)
from modules.core.src.capabilities_observability_setup import (
    _start_span as _obs_start_span,
)
from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.shared.src import AppConfig
from modules.shared.src.utility_core_validation import validate_file as _util_validate_file


def write_output(
    path, content: str, ctx, src: str, dur: float, input_chars: int, output_chars: int, config=None
) -> None:
    """Standalone wrapper for Saver.write_output."""
    Saver().write_output(path, content, ctx, src, dur, input_chars, output_chars, config)


def click_send(page, emitter=None, config=None) -> None:
    """Standalone wrapper for SendDispatcher.click_send."""
    SendDispatcher().click_send(page, emitter, config=config)


def _configure_sentry() -> None:
    """Standalone wrapper for ObservabilitySetup._configure_sentry."""
    ObservabilitySetup._configure_sentry(ObservabilitySetup(Path("/tmp")))


def _configure_tracing() -> None:
    """Standalone wrapper for ObservabilitySetup._configure_tracing."""
    ObservabilitySetup._configure_tracing(ObservabilitySetup(Path("/tmp")))


def _configure_logging(log_path: Path) -> None:
    """Standalone wrapper for ObservabilitySetup._configure_logging."""
    ObservabilitySetup._configure_logging(ObservabilitySetup(Path("/tmp")), log_path)


def bind_run_context(run_id: str, **extra) -> None:
    """Standalone wrapper for private module function."""
    _obs_bind(run_id, **extra)


def clear_run_context() -> None:
    """Standalone wrapper for private module function."""
    _obs_clear()


def get_logger(name="qwen-web"):
    """Standalone wrapper for private module function."""
    return _obs_get_logger(name)


def get_tracer(name="qwen-web"):
    """Standalone wrapper for private module function."""
    return _obs_get_tracer(name)


def start_span(name):
    """Standalone wrapper for private module function."""
    return _obs_start_span(name)


def _close_dropdown_if_open(page) -> None:
    """Standalone wrapper for FileUploader._close_dropdown_if_open."""
    FileUploader()._close_dropdown_if_open(page)


def upload_attachment(page, filepath) -> bool:
    """Standalone wrapper for FileUploader.upload_attachment."""
    return FileUploader().upload_attachment(page, filepath)


def validate_file(filepath, max_size_mb=100.0):
    """Standalone wrapper for utility function."""
    return _util_validate_file(filepath, max_size_mb)


def clean_stale_locks(user_data_dir: str) -> None:
    """Standalone wrapper for BrowserAdapter._clean_stale_locks."""
    BrowserAdapter()._clean_stale_locks(user_data_dir)


def navigate_to_chat(page, emitter) -> None:
    """Standalone wrapper for BrowserAdapter.navigate_to_chat."""
    BrowserAdapter().navigate_to_chat(page, emitter)


def make_app_config(tmp_path: Path, **overrides) -> AppConfig:
    """Build an AppConfig rooted at tmp_path with a default test layout."""
    defaults = dict(
        mode="batch",
        input_path=tmp_path / "input",
        output_path=tmp_path / "output",
        done_path=tmp_path / "input" / "done",
        failed_path=tmp_path / "input" / "failed",
        proc_path=tmp_path / "input" / ".processing",
        session_path=tmp_path / "session",
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator


def make_test_orchestrator(**overrides) -> DirectPromptOrchestrator:
    """Build a DirectPromptOrchestrator with all dependencies mocked."""
    defaults = dict(
        browser=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
    )
    defaults.update(overrides)
    return DirectPromptOrchestrator(**defaults)  # type: ignore[arg-type]
