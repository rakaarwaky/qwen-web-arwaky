"""Regression tests for the approved UX remediation findings.

Covers the TUI-side findings that pin the shipped behaviour:

- UX-3-002 — the canonical failure glyph ``✗`` (U+2717) is the one object
  the CLI and the TUI read; no TUI status label carries the stray ``✕``.
- UX-3-003 — ``NO_COLOR`` is a colour preference and must not affect
  iconography; only the locale gate picks the ASCII fallback.
- UX-4-002 — ``r`` / ``e`` / ``d`` are Sessions-pane-gated, the same gate
  the ↑/↓ row keys already use; ``a`` stays global.
- UX-5-001 — one English empty-state string for the session list, read from
  the single shared constant on a cold render and after a repaint.
- UX-1-001 — a non-usable session verdict pairs its log line with an
  ``ACTION:`` line naming ``ctrl+l``; ``VALID`` does not.
- UX-1-003 — a failed login writes the explicit retry line; a successful
  login does not.
- UX-2-002 — the slot carousel has three label tiers (full / compact /
  minimal) selected from an injected width budget.
- UX-1-002 — the key-hint strip renders under the session table on a cold
  start and survives a ``_refresh_sessions_table`` repaint.
- UX-5-003 — the Swarm primary CTA reads ``▶ START`` cold and flips to
  ``↻ RESTART`` once a run registers.

Every test injects the width budget / environment it needs, so nothing
here depends on the host terminal, the host's ``NO_COLOR``, or a real
controlling TTY.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from textual.worker import WorkerFailed

from modules.tui.src.surface_tui_utils_component import (
    _CANONICAL_FAIL_GLYPH,
    _EVENT_BADGE,
    _STATUS_BADGE,
    _STATUS_TABLE,
    SESSION_EMPTY_HINT,
    _TuiUtilsMixin,
)


def _make_app() -> Any:
    from modules.tui.src.surface_tui_app_screen import QwenTuiApp

    return QwenTuiApp(
        workspace=MagicMock(),
        prompt=MagicMock(),
        slot_config=MagicMock(),
        session=MagicMock(),
        jobs=MagicMock(),
        updater=MagicMock(),
        job_storage=MagicMock(),
    )


class _ScreenSizeStub:
    def __init__(self, width: int) -> None:
        self.width = width


class TestCanonicalFailureGlyph:
    """UX-3-002: one ``✗`` across the CLI and the TUI."""

    def test_the_cli_and_the_tui_read_the_same_glyph_object(self) -> None:
        from modules.cli.src.surface_cli_json_hook import STATUS_GLYPHS as CLI_GLYPHS
        from modules.shared.src.common.taxonomy_core_constant import STATUS_GLYPHS as SHARED_GLYPHS

        assert CLI_GLYPHS is SHARED_GLYPHS, "the CLI surface must re-export the shared object"
        assert SHARED_GLYPHS["fail"] == "✗"
        assert _CANONICAL_FAIL_GLYPH is SHARED_GLYPHS["fail"], "the TUI must read the same object"

    def test_the_tui_failed_labels_carry_the_canonical_glyph(self) -> None:
        assert "✗" in _STATUS_BADGE["FAILED"]
        assert "✗" in _STATUS_TABLE["FAILED"]
        assert "✗" in _EVENT_BADGE["FAILED"]

    def test_no_tui_failed_label_carries_the_stray_ballot_x(self) -> None:
        for label in (_STATUS_BADGE["FAILED"], _STATUS_TABLE["FAILED"], _EVENT_BADGE["FAILED"]):
            assert "✕" not in label, f"the stray U+2715 marker survived in {label!r}"

    def test_the_finalize_slot_tab_title_uses_the_canonical_glyph(self) -> None:
        from modules.tui.src.surface_tui_workers_store import _TuiWorkersMixin

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                _TuiWorkersMixin._finalize_slot(app, 1, "FAILED", "task.md", 1.0, False, 0)
                from textual.widgets import TabbedContent

                tab = app.query_one(TabbedContent).get_tab("tab-slot-1")
                assert "✗" in str(tab.label), f"tab title must carry ✗, got {tab.label!r}"
                assert "✕" not in str(tab.label)

        asyncio.run(_run())


class TestGlyphCapabilityIsLocaleGated:
    """UX-3-003: NO_COLOR must not disable the wide glyphs."""

    def test_no_color_with_a_utf8_locale_still_yields_the_wide_glyph(self) -> None:
        with patch.dict(
            os.environ,
            {"NO_COLOR": "1", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"},
            clear=False,
        ):
            assert _TuiUtilsMixin._glyph("refresh") == "↻"
            assert _TuiUtilsMixin._unicode_ok() is True

    def test_forced_ascii_locale_yields_the_ascii_fallback(self) -> None:
        with patch.dict(os.environ, {"LC_ALL": "C", "LANG": "C"}, clear=False):
            assert _TuiUtilsMixin._glyph("refresh") == "r"
            assert _TuiUtilsMixin._unicode_ok() is False

    def test_no_color_is_not_consulted_even_without_a_locale(self) -> None:
        env = {"NO_COLOR": "1"}
        with patch.dict(os.environ, env, clear=True):
            assert _TuiUtilsMixin._unicode_ok() is True
            assert _TuiUtilsMixin._glyph("delete") == "×"


class TestSessionKeysAreSessionsPaneGated:
    """UX-4-002: r/e/d are no-ops outside the Sessions pane."""

    def test_refresh_edit_and_delete_are_noops_off_the_sessions_pane(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                from textual.widgets import TabbedContent

                app.query_one(TabbedContent).active = "tab-overview"
                await pilot.pause(0.1)
                assert app._sessions_active() is False

                with (
                    patch.object(app, "_refresh_sessions_table") as mock_refresh,
                    patch.object(app, "_run_session_health_check") as mock_health,
                    patch.object(app, "_account_button_pressed") as mock_delete,
                    patch.object(app, "_log_msg") as mock_log,
                ):
                    app.action_session_refresh()
                    app.action_session_edit()
                    app.action_session_delete()
                    mock_refresh.assert_not_called()
                    mock_health.assert_not_called()
                    mock_delete.assert_not_called()
                    mock_log.assert_not_called()

        asyncio.run(_run())

    def test_refresh_edit_and_delete_still_work_on_the_sessions_pane(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                from textual.widgets import TabbedContent

                app.query_one(TabbedContent).active = "tab-sessions"
                await pilot.pause(0.1)
                assert app._sessions_active() is True

                with (
                    patch.object(app, "_refresh_sessions_table") as mock_refresh,
                    patch.object(app, "_run_session_health_check") as mock_health,
                ):
                    app.action_session_refresh()
                    mock_refresh.assert_called_once()
                    # No row selected: the in-pane guidance still logs and
                    # the whole-pool health check still runs.
                    app.action_session_edit()
                    mock_health.assert_called_once()
                    app.action_session_delete()
                    mock_health.assert_called_once()

        asyncio.run(_run())

    def test_add_stays_global_off_the_sessions_pane(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                from textual.widgets import TabbedContent

                app.query_one(TabbedContent).active = "tab-overview"
                await pilot.pause(0.1)
                with patch.object(app, "action_session_add_new") as mock_add:
                    app.action_session_add()
                    mock_add.assert_called_once()

        asyncio.run(_run())


class TestOneSessionEmptyHint:
    """UX-5-001: one English empty-state string in all three places."""

    def test_the_compose_tree_renders_the_shared_string(self) -> None:
        from textual.containers import Vertical
        from textual.widgets import Label

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                rows = app.query_one("#session-rows", Vertical)
                empty = rows.query_one(".session-empty", Label)
                assert str(empty.content) == SESSION_EMPTY_HINT
                # The Indonesian wording and the duplicate English one are both gone.
                assert "Belum ada" not in str(empty.content)
                assert "No accounts registered" not in str(empty.content)

        asyncio.run(_run())

    def test_a_repaint_renders_the_same_string_and_widget(self) -> None:
        from textual.containers import Vertical
        from textual.widgets import Label

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app._render_account_cards([])
                rows = app.query_one("#session-rows", Vertical)
                empty = rows.query_one(".session-empty", Label)
                assert str(empty.content) == SESSION_EMPTY_HINT

        asyncio.run(_run())

    def test_no_non_english_or_duplicate_string_remains_in_the_pane(self) -> None:
        from textual.widgets import Label

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                texts = [str(w.content) for w in app.query(Label)]
                joined = "\n".join(texts)
                assert "Belum ada" not in joined
                assert "No accounts registered" not in joined
                assert "tekan A untuk menambah" not in joined

        asyncio.run(_run())


class TestSessionStateActionCallToAction:
    """UX-1-001: non-usable verdicts pair an ACTION line with the verdict."""

    def test_a_non_usable_verdict_writes_the_verdict_and_the_action_line(self) -> None:
        app = _make_app()
        written: list[str] = []
        app._log_msg = lambda msg, *a, **k: written.append(str(msg))

        for state in ("EXPIRED", "N/A", "TIMEOUT"):
            written.clear()
            app._apply_session_state(state)
            assert any("SESSION:" in line and state in line for line in written), written
            assert any("ACTION:" in line and "ctrl+l" in line for line in written), written

    def test_a_valid_verdict_writes_only_the_verdict_line(self) -> None:
        app = _make_app()
        written: list[str] = []
        app._log_msg = lambda msg, *a, **k: written.append(str(msg))

        app._apply_session_state("VALID")
        assert len(written) == 1, written
        assert "SESSION:" in written[0]
        assert "VALID" in written[0]
        assert not any("ACTION:" in line for line in written), written


class TestLoginFailureRetryGuidance:
    """UX-1-003: the failure branch writes the retry line, the success branch does not."""

    def _session_stub(self, *, valid: bool, error: str | None = None) -> MagicMock:
        session = MagicMock()
        response = MagicMock()
        response.valid = valid
        response.error = error
        response.message = None
        response.profile_path = None
        session.execute.return_value = response
        return session

    def test_the_failure_branch_writes_the_retry_line(self) -> None:
        app = _make_app()
        app._session = self._session_stub(valid=False, error="browser closed early")
        written: list[str] = []
        app._log_msg = lambda msg, *a, **k: written.append(str(msg))

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                with patch.object(app, "notify"):
                    worker = app._run_add_session_worker("work")
                    if worker is not None:
                        with contextlib.suppress(WorkerFailed):
                            await worker.wait()

        asyncio.run(_run())
        assert any("LOGIN FAILED:" in line for line in written), written
        assert any("ACTION:" in line and "Press A (or ADD SESSION) to retry login" in line for line in written), written

    def test_the_success_branch_writes_no_retry_line(self) -> None:
        app = _make_app()
        app._session = self._session_stub(valid=True)
        written: list[str] = []
        app._log_msg = lambda msg, *a, **k: written.append(str(msg))

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                with patch.object(app, "notify"):
                    worker = app._run_add_session_worker("work")
                    if worker is not None:
                        with contextlib.suppress(WorkerFailed):
                            await worker.wait()

        asyncio.run(_run())
        assert any("SUCCESS:" in line for line in written), written
        assert not any("to retry login" in line for line in written), written


class TestSlotCarouselTiers:
    """UX-2-002: full, compact, and minimal label tiers."""

    def _pane_chips(self, app: Any) -> list[Any]:
        """The chips of one pane's carousel, not every pane's."""
        from textual.containers import Horizontal

        carousel = app.query_one("#tab-slot-1 .slot-carousel", Horizontal)
        return list(carousel.query(".slot-chip"))

    def _labels_after_refresh(self, app: Any, screen_width: int) -> list[str]:
        with patch.object(type(app.screen), "size", new_callable=_ScreenSizeStub, width=screen_width):
            app._refresh_slot_chips()
        return [str(chip.label) for chip in self._pane_chips(app)]

    def test_at_60_columns_every_chip_carries_the_compact_or_numeric_label(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                labels = self._labels_after_refresh(app, 60)
                chips = self._pane_chips(app)
                assert len(chips) == app._NUM_SLOTS, "one carousel carries NUM_SLOTS chips"
                assert len(labels) == app._NUM_SLOTS
                for label in labels:
                    assert label.startswith("● ") or label.isdigit(), (
                        f"expected a compact or numeric label, got {label!r}"
                    )
                    assert "SLOT" not in label, "the full word must drop at 60 columns"

        asyncio.run(_run())

    def test_at_42_columns_the_minimal_tier_renders_bare_numbers(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                labels = self._labels_after_refresh(app, 42)
                chips = self._pane_chips(app)
                assert len(chips) == app._NUM_SLOTS
                for label in labels:
                    assert label.isdigit(), f"the minimal tier renders the bare number, got {label!r}"

        asyncio.run(_run())

    def test_at_180_columns_the_full_label_renders(self) -> None:
        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                labels = self._labels_after_refresh(app, 180)
                for label in labels:
                    assert label.startswith("● SLOT "), f"expected the full label, got {label!r}"

        asyncio.run(_run())


class TestSessionKeyHintStrip:
    """UX-1-002: the key-hint strip under the session table."""

    def test_the_strip_renders_on_a_cold_start(self) -> None:
        from textual.widgets import Label

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                hint = app.query_one(".session-key-hint", Label)
                assert hint.has_class("session-key-hint")
                text = str(hint.content)
                for fragment in ("↑/↓ select row", "A add", "R refresh", "E health", "D delete", "?"):
                    assert fragment in text, f"the hint strip must carry {fragment!r}, got {text!r}"

        asyncio.run(_run())

    def test_the_strip_survives_a_table_repaint(self) -> None:
        from textual.widgets import Label

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                with patch.object(app, "_account_card", return_value=MagicMock()):
                    app._render_account_cards([])
                hints = list(app.query(".session-key-hint"))
                assert len(hints) == 1, "the strip must not be duplicated or removed by a repaint"
                assert isinstance(hints[0], Label)

        asyncio.run(_run())

    def test_the_strip_is_painted_on_a_short_terminal(self) -> None:
        from textual.widgets import Label, TabbedContent

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(80, 24)) as pilot:
                # Switch to the Sessions pane where the key-hint strip lives.
                app.query_one(TabbedContent).active = "tab-sessions"
                await pilot.pause(0.2)
                strips = list(app.screen._compositor.render_strips())
                rendered = "".join(s.text for s in strips)
                assert "select row" in rendered, (
                    f"the key-hint strip must be painted on an 80x24 terminal, got strips: {[s.text for s in strips]}"
                )
                hint = app.query_one(".session-key-hint", Label)
                assert hint.region.height > 0, "the hint must have a non-zero rendered region"

        asyncio.run(_run())


class TestSwarmStartLabel:
    """UX-5-003: the primary CTA label carries the run state."""

    def test_the_cold_start_label_is_start(self) -> None:
        from textual.widgets import Button

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                label = app.query_one("#btn-swarm-start", Button)
                assert str(label.label) == "▶ START", f"cold-start label, got {label.label!r}"

        asyncio.run(_run())

    def test_a_registered_run_flips_the_label_to_restart(self) -> None:
        from textual.widgets import Button

        app = _make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app._set_swarm_start_label("↻ RESTART")
                label = app.query_one("#btn-swarm-start", Button)
                assert str(label.label) == "↻ RESTART"

        asyncio.run(_run())

    def test_the_swarm_worker_flips_the_label_when_a_run_registers(self) -> None:
        from textual.widgets import Button

        app = _make_app()
        swarm = MagicMock()
        snapshot = MagicMock()
        snapshot.swarm_id = "swarm-1"
        snapshot.agents = ()
        snapshot.status = "completed"
        snapshot.completed_count = 0
        snapshot.failed_count = 0
        snapshot.browser_concurrency = 2
        response = MagicMock()
        response.snapshot = snapshot
        swarm.execute.return_value = response
        app._swarm = swarm

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                with patch.object(app, "call_from_thread", _sync_call_from_thread(app)):
                    worker = app._swarm_worker(Path("/in"))
                    if worker is not None:
                        with contextlib.suppress(WorkerFailed):
                            await worker.wait()
                label = app.query_one("#btn-swarm-start", Button)
                assert str(label.label) == "↻ RESTART", f"got {label.label!r}"

        asyncio.run(_run())


def _sync_call_from_thread(app: Any):
    def _cft(callback, *args, **kwargs):
        callback(*args, **kwargs)
        return None

    return _cft


__all__ = [
    "TestCanonicalFailureGlyph",
    "TestGlyphCapabilityIsLocaleGated",
    "TestSessionKeysAreSessionsPaneGated",
    "TestOneSessionEmptyHint",
    "TestSessionStateActionCallToAction",
    "TestLoginFailureRetryGuidance",
    "TestSlotCarouselTiers",
    "TestSessionKeyHintStrip",
    "TestSwarmStartLabel",
]
