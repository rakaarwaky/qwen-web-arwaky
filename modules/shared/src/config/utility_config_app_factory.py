"""
Utility layer (utility_core_config_factory): build AppConfig and derive paths.
Stateless functions consumed by Agent orchestrator and StatusFileWriter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_SEND_CLICK_TIMEOUT_MS,
    DEFAULT_SESSION,
    REQUEST_TIMEOUT_ENV,
    SEND_CLICK_TIMEOUT_ENV,
    TRUE_VALUES,
)
from modules.shared.src.common.taxonomy_core_vo import AppConfig


def _resolve_request_timeout(override: int) -> int:
    """Resolve the response-wait ceiling from the env override or the default."""
    raw = os.environ.get(REQUEST_TIMEOUT_ENV, "").strip()
    if not raw:
        return override
    try:
        parsed = int(raw)
    except ValueError:
        return override
    return parsed if parsed > 0 else override


def _resolve_send_click_timeout_ms() -> int:
    """Resolve the attachment send ceiling from the env or the default.

    ``QWEN_SEND_CLICK_TIMEOUT_MS`` overrides the ceiling per environment
    (FRD Assumptions). Unparseable or non-positive values keep
    ``DEFAULT_SEND_CLICK_TIMEOUT_MS`` so a malformed override cannot
    disable the send wait.
    """
    raw = os.environ.get(SEND_CLICK_TIMEOUT_ENV, "").strip()
    if not raw:
        return DEFAULT_SEND_CLICK_TIMEOUT_MS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_SEND_CLICK_TIMEOUT_MS
    return parsed if parsed > 0 else DEFAULT_SEND_CLICK_TIMEOUT_MS


def sandbox_unavailable() -> bool:
    """Return True when the Linux host cannot host Chromium's OS sandbox.

    The sandbox needs seccomp-bpf and/or unprivileged user namespaces. A
    container or a hardened host can lack either; in that case Chromium
    refuses to start unless ``--no-sandbox`` is passed (issue #290).
    """
    if sys.platform != "linux":
        return False
    try:
        status = Path("/proc/self/status").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    seccomp: int | None = None
    for line in status.splitlines():
        if line.startswith("Seccomp:"):
            parts = line.split()
            if len(parts) == 2 and parts[1].isdigit():
                seccomp = int(parts[1])
            break
    if seccomp is None or seccomp == 0:
        # Field missing or seccomp filter disabled: no seccomp sandbox support.
        return True
    for sysctl in (
        Path("/proc/sys/kernel/unprivileged_userns_clone"),
        Path("/proc/sys/user/max_user_namespaces"),
    ):
        try:
            if sysctl.exists() and sysctl.read_text(encoding="utf-8").strip() == "0":
                return True
        except OSError:
            continue
    return False


def build_app_config(
    mode: str = "",
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
    headless: bool = True,
    interval: int = 3,
    session_path: Path | str | None = None,
    log_path: Path | None = None,
    timeout: int = 300,
    prompt_file: Path | None = None,
    prompt_path: Path | None = None,
    file_path: Path | None = None,
    chrome_profile: str = "qwen-cli-profile",
    storage_state_file: Path | None = None,
    disable_sandbox: bool = False,
    request_timeout: int = 600,
    poll_interval: float = 1.0,
    streaming_timeout: int = 180,
    rate_limit_per_minute: int = 60,
    circuit_breaker_threshold: int = 5,
    circuit_breaker_window: int = 30,
    retry_failed: bool = False,
    model: str = "",
) -> AppConfig:
    """Build a complete AppConfig while preserving every runtime override.

    The Chromium OS sandbox stays enabled by default (issue #290). It is
    dropped only when the caller passes ``disable_sandbox=True``, an explicit
    env switch is set, or the Linux host is detected as unable to support the
    sandbox. ``QWEN_ENABLE_SANDBOX`` forces the sandbox on;
    ``QWEN_DISABLE_SANDBOX`` forces it off.
    """
    dummy_path = Path(os.devnull)
    if os.environ.get("QWEN_DISABLE_SANDBOX", "").lower() in TRUE_VALUES:
        disable_sandbox = True
    elif os.environ.get("QWEN_ENABLE_SANDBOX", "").lower() in TRUE_VALUES:
        disable_sandbox = False
    elif not disable_sandbox and sandbox_unavailable():
        disable_sandbox = True
    # Normalise a raw string profile argument to a Path; fall back to the
    # shared default when the caller supplied nothing.
    session_path = Path(session_path) if isinstance(session_path, str) else (session_path or DEFAULT_SESSION)
    return AppConfig(
        mode=mode,
        input_path=input_path or dummy_path,
        output_path=output_path or DEFAULT_OUTPUT,
        session_path=session_path,
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
        request_timeout=_resolve_request_timeout(request_timeout),
        send_click_timeout_ms=_resolve_send_click_timeout_ms(),
        poll_interval=poll_interval,
        streaming_timeout=streaming_timeout,
        rate_limit_per_minute=rate_limit_per_minute,
        circuit_breaker_threshold=circuit_breaker_threshold,
        circuit_breaker_window=circuit_breaker_window,
        retry_failed=retry_failed,
        model=model,
    )


def resolve_pipeline_output_path(
    prompt_file: Path | str,
    output_file: Path | str | None = None,
    attachment_path: Path | str | None = None,
    stem: str | None = None,
) -> tuple[Path, Path]:
    """Resolve prompt file and output file paths cleanly for prompt pipeline agents.

    ``output_file`` semantics
    ------------------------
    * ``None`` (default) → auto-name the destination under ``DEFAULT_OUTPUT``
      as ``{stem}_{YYYYMMDD-HHMMSS}_{hex4}.md`` so concurrent slot runs that
      start in the same second never overwrite each other (issue #280 AC-1).
    * A **non-directory path**, with or without an extension → honored exactly
      as the operator supplied it. No timestamp or hex suffix is appended;
      repeated runs overwrite the same file. Collision safety is the
      operator's choice.
    * A **directory path** → auto-name a file inside it, using the same
      ``{stem}_{YYYYMMDD-HHMMSS}_{hex4}.md`` form as the default case.

    The stem is ``stem`` when given, otherwise the attachment's stem when
    ``attachment_path`` is provided, otherwise the prompt's stem. Direct
    prompts materialize their text as a ``tmpXXXX`` file, so they pass
    ``DIRECT_PROMPT_STEM`` and never leak that throwaway name into the
    output directory.
    """
    import uuid
    from datetime import datetime

    p_path = Path(prompt_file).resolve()
    if not p_path.is_file():
        raise FileNotFoundError(f"Input file not found or is a directory: {p_path}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # 4 hex digits from 16 random bits: collision-safe for concurrent slot
    # runs without making filenames unwieldy, and free of separators that
    # would need escaping on any supported platform.
    unique = uuid.uuid4().hex[:4]

    # Explicit stem wins; otherwise prefer attachment stem; fall back to prompt stem.
    if stem is not None:
        resolved_stem = stem
    elif attachment_path:
        resolved_stem = Path(attachment_path).stem
    else:
        resolved_stem = p_path.stem

    if output_file:
        out_path = Path(output_file).resolve()
        # A user-supplied -o path is honored exactly as named: the operator
        # chose the destination, so write to that precise path in place. No
        # timestamp or hex suffix is appended; repeated runs overwrite the
        # same file (issue #280 AC-1 collision safety applies only to
        # auto-generated names). A directory argument still auto-completes a
        # unique filename inside it.
        out_path = out_path / f"{resolved_stem}_{ts}_{unique}.md" if out_path.is_dir() else out_path
    else:
        out_path = DEFAULT_OUTPUT / f"{resolved_stem}_{ts}_{unique}.md"

    return p_path, out_path
