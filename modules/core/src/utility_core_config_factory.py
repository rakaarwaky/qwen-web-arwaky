"""
Utility layer (utility_core_config_factory): build AppConfig and derive paths.
Stateless functions consumed by Agent orchestrator and StatusFileWriter.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_SESSION,
)
from modules.shared.src.taxonomy_core_vo import AppConfig


def build_app_config(
    mode: str = "",
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
    headless: bool = True,
    interval: int = 3,
    done_path: Path | None = None,
    failed_path: Path | None = None,
    proc_path: Path | None = None,
    session_path: Path | None = None,
    log_path: Path | None = None,
    timeout: int = 300,
    prompt_file: Path | None = None,
    prompt_path: Path | None = None,
    file_path: Path | None = None,
    chrome_profile: str = "qwen-cli-profile",
    storage_state_file: Path | None = None,
    disable_sandbox: bool = True,
    request_timeout: int = 120,
    poll_interval: float = 1.0,
    streaming_timeout: int = 180,
    rate_limit_per_minute: int = 60,
    circuit_breaker_threshold: int = 5,
    circuit_breaker_window: int = 30,
    retry_failed: bool = False,
) -> AppConfig:
    """Build a complete AppConfig while preserving every runtime override."""
    dummy_path = Path(os.devnull)
    return AppConfig(
        mode=mode,
        input_path=input_path or dummy_path,
        output_path=output_path or DEFAULT_OUTPUT,
        done_path=done_path or dummy_path,
        failed_path=failed_path or dummy_path,
        proc_path=proc_path or dummy_path,
        session_path=session_path or DEFAULT_SESSION,
        log_path=log_path or DEFAULT_LOG,
        interval=interval,
        timeout=timeout,
        headless=headless,
        prompt_file=prompt_file,
        prompt_path=prompt_path,
        file_path=file_path,
        chrome_profile=chrome_profile,
        storage_state_file=storage_state_file,
        disable_sandbox=disable_sandbox,
        request_timeout=request_timeout,
        poll_interval=poll_interval,
        streaming_timeout=streaming_timeout,
        rate_limit_per_minute=rate_limit_per_minute,
        circuit_breaker_threshold=circuit_breaker_threshold,
        circuit_breaker_window=circuit_breaker_window,
        retry_failed=retry_failed,
    )


def resolve_pipeline_output_path(
    prompt_file: Path | str,
    output_file: Path | str | None = None,
    attachment_path: Path | str | None = None,
) -> tuple[Path, Path]:
    """Resolve prompt file and output file paths cleanly for prompt pipeline agents.

    The output filename is derived from the attachment path (when provided),
    otherwise from the prompt filename. In all cases the output name receives
    a timestamp suffix so repeated runs never silently overwrite each other.
    """
    from datetime import datetime

    p_path = Path(prompt_file).resolve()
    if not p_path.is_file():
        raise FileNotFoundError(f"Input file not found or is a directory: {p_path}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Prefer attachment stem; fall back to prompt stem when there is no attachment.
    stem = Path(attachment_path).stem if attachment_path else p_path.stem

    if output_file:
        out_path = Path(output_file).resolve()
        if out_path.is_dir():
            out_path = out_path / f"{stem}_{ts}.md"
        elif out_path.exists():
            out_path = out_path.parent / f"{out_path.stem}_{ts}{out_path.suffix}"
        else:
            out_path = out_path.parent / f"{stem}_{ts}{out_path.suffix}"
    else:
        out_path = DEFAULT_OUTPUT / f"{stem}_{ts}.md"

    return p_path, out_path
