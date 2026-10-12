"""Regression tests for the session-check watchdog timer.

The 60-second timer armed by ``_check_session`` must be stopped as soon as
the verdict callback (``_apply_session_state``) lands.  Without that, a
successful check is followed by a spurious ``Session check timed out``
warning even though ``EVENT_LOGIN_VERIFIED`` already reported a valid
session — the exact log the user filed. The window is 60s because a
legitimate successful validation (including up to ~25s of model-picker
retries in ``navigate_to_chat``) takes ~30s; the old 15s window fired
before that.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from textual.timer import Timer

from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
from modules.tui.src.surface_tui_app import QwenTuiApp


class _ValidSession:
    """Session mock that reports a valid stored session.

    Declared as ``MagicMock``-compatible: the app type-hints ``session`` as
    ``ISessionAggregate | None`` but the test only needs the ``execute``
    protocol, so a bare duck-typed object is what other tests in this file
    already use.
    """

    def execute(self, request):
        response = MagicMock()
        response.valid = True
        return response


def _make_app() -> QwenTuiApp:
    app = QwenTuiApp(
        workspace=MagicMock(),
        direct=MagicMock(),
        file_only=MagicMock(),
        attachment=MagicMock(),
        slot_config=SlotRunPlanResolver(),
        session_manager=MagicMock(),
        session=_ValidSession(),
    )
    return app


def test_no_spurious_timeout_after_successful_check() -> None:
    """A valid verdict stops the watchdog, so no timeout warning follows."""
    app = _make_app()

    log_lines: list[str] = []
    app._log_msg = lambda text, *a, **k: log_lines.append(str(text))
    app.notify = lambda *a, **k: log_lines.append(f"NOTIFY:{k.get('title')}")

    async def _run() -> None:
        async with app.run_test(size=(150, 44)) as pilot:
            armed: dict[str, object] = {}
            real_set_timer = pilot.app.set_timer

            def _arm(seconds: float, callback) -> Timer:
                armed["seconds"] = seconds
                t = real_set_timer(seconds, callback)
                armed["timer"] = t
                return t

            app.set_timer = _arm
            app._check_session()
            # The armed timer must target the 60s window.
            assert armed["seconds"] == 60.0, f"unexpected watchdog duration {armed['seconds']}"
            # Let the verdict land.
            for _ in range(6):
                await pilot.pause(0.25)
            assert app._last_session_state == "VALID", app._last_session_state
            assert app._session_check_timer is None, "watchdog still armed"
            # Now let the original 60s window fully elapse.
            await pilot.pause(61.0)

    asyncio.run(_run())

    timeouts = [line for line in log_lines if "timed out" in line.lower()]
    assert timeouts == [], f"spurious timeout warning: {timeouts}"


def test_timer_stops_when_verdict_lands() -> None:
    """_apply_session_state itself must disarm the watchdog."""
    app = _make_app()

    timer = MagicMock()
    app._session_check_timer = timer

    app._apply_session_state("VALID")

    timer.stop.assert_called_once()
    assert app._session_check_timer is None


def test_timeout_path_sets_state_and_flag() -> None:
    """When the watchdog fires first, the state is TIMEOUT and the flag is set."""
    app = _make_app()
    app._session_check_timer = None
    app._session_check_timed_out = False

    app._session_check_timeout()

    assert app._last_session_state == "TIMEOUT"
    assert app._session_check_timed_out is True
