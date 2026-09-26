"""Agent: build runtime configuration for every feature orchestrator.

Eight call sites used to import ``build_app_config`` directly, which put the
sandbox probe and the request-timeout environment override behind a module-level
import no test could substitute. This orchestrator makes config construction an
injected dependency, so the environment-derived policy has one owner and one
seam.
"""

from __future__ import annotations

from pathlib import Path

from modules.core.src.utility_core_config_factory import build_app_config
from modules.shared.src.contract_core_aggregate import IConfigAggregate
from modules.shared.src.taxonomy_core_vo import AppConfig, Mode, TimeoutSec

__all__ = ["ConfigOrchestrator"]


class ConfigOrchestrator(IConfigAggregate):
    """Build ``AppConfig`` values on behalf of the other orchestrators."""

    def __init__(self) -> None:
        """Bind the config factory.

        The factory is a module-level function, so it is held rather than
        injected; every behavior that varies per host already lives inside it.
        """
        self._build = build_app_config

    def for_mode(
        self,
        mode: Mode = Mode(""),
        *,
        input_path: Path | None = None,
        output_path: Path | None = None,
        headless: bool = True,
        session_path: Path | None = None,
        prompt_file: Path | None = None,
        file_path: Path | None = None,
        model: str = "",
    ) -> AppConfig:
        """Build an ``AppConfig`` for ``mode`` with the given overrides.

        Fields the caller leaves out fall back to the shared defaults, and the
        factory still applies the host's sandbox and timeout policy on top, so a
        caller cannot obtain a config that ignores the operator's environment.
        """
        return self._build(
            str(mode),
            input_path=input_path,
            output_path=output_path,
            headless=headless,
            session_path=session_path,
            prompt_file=prompt_file,
            file_path=file_path,
            model=model,
        )

    def request_timeout_sec(self) -> TimeoutSec:
        """Return the response-wait ceiling the host's environment sets.

        Reported separately from :meth:`for_mode` because the stream monitor
        and the surface status line both need the effective value without
        building a whole config, and reading it once keeps the two in step with
        the environment override.
        """
        return TimeoutSec(self._build().request_timeout)
