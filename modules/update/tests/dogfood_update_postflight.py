"""Dogfood tests for the postflight health checks against the real host.

These run the postflight checks the update path uses to decide whether an
upgraded install is acceptable, so the host probes are exercised against
this machine rather than a stub. No upgrade runs and no network is touched.
"""

from __future__ import annotations

from modules.update.src.capabilities_update_manager import UpdateManager


def _postflight() -> tuple[str, ...]:
    """Return the names of the postflight steps and their outcomes."""
    manager = UpdateManager()
    return tuple(f"{step.name}={'ok' if step.success else 'failed'}" for step in manager._postflight_health_checks())


def test_dogfood_postflight_reports_named_steps() -> None:
    steps = _postflight()

    assert steps, "the postflight must report at least one named step, not a bare boolean"


def test_dogfood_postflight_reports_the_chromium_build() -> None:
    names = " ".join(_postflight())

    assert "chromium" in names or "browser" in names, (
        "the postflight must prove the managed browser build, which is the step an upgrade breaks first"
    )


def test_dogfood_postflight_is_repeatable() -> None:
    """The postflight runs on every upgrade, so two runs on an unchanged
    host must agree rather than flap."""
    assert _postflight() == _postflight()
