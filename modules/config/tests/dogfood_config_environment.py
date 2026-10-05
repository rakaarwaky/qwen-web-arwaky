"""Dogfood tests for the config environment seam.

These exercise the environment-driven verdicts the pipeline reads before a
run: the sandbox mode, the response-wait ceiling, and the worker cap. They
need no network and no browser, only the host's own signals.
"""

from __future__ import annotations

from modules.config.src.capabilities_config_environment import ConfigEnvironment


def test_dogfood_sandbox_verdict_names_a_known_state() -> None:
    verdict = ConfigEnvironment().sandbox_report()

    assert verdict.state in {"sandboxed", "disabled_by_env", "disabled_by_host", "forced"}
    assert verdict.reason, "a verdict must name the reason it was chosen"


def test_dogfood_response_ceiling_is_positive() -> None:
    assert ConfigEnvironment().request_timeout_sec() > 0


def test_dogfood_worker_cap_is_positive() -> None:
    assert ConfigEnvironment().max_workers() >= 1
