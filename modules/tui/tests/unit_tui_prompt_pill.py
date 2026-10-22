"""Regression tests for the Prompt pill (FE-3-01).

The Prompt pill used to write its picked path into the slot's composer
Input. The composer is read as the *prompt source*, so Send dispatched the
path string via ``process_direct_prompt`` and Qwen received
``/home/user/prompts/task.md`` instead of the file's contents.

The pill must store the path in per-slot state, keep the composer free of
paths, and route Send through ``process_prompt_file_only`` when the file
is set and the composer is empty. A dual input (file + typed text, or
file + attachment) is refused, not merged.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from unittest.mock import MagicMock

from textual.widgets import Input, Label
from textual.worker import WorkerFailed

from modules.tui.src.surface_tui_app_screen import QwenTuiApp
from modules.tui.tests.fixture_tui_app import make_app


def _wire_sync_cft(app: QwenTuiApp) -> None:
    def _cft(callback, *args, **kwargs):
        callback(*args, **kwargs)
        return None

    app.call_from_thread = _cft


class TestPromptPillRouting:
    """The Prompt pill opens the prompt-file picker, never the composer Input."""

    def test_pill_routes_to_prompt_file_picker_and_composer_stays_empty(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                picked = tmp_path / "refactor_task.md"
                picked.write_text("Do the refactor", encoding="utf-8")

                from textual.widgets import Button

                app.query_one("#btn-pill-prompt-1", Button).press()
                await pilot.pause(0.05)
                app.screen.dismiss(str(picked))
                for _ in range(5):
                    await pilot.pause(0.02)

                assert app._slot_prompt_files[1] == str(picked)
                assert app.query_one("#composer-1", Input).value == ""
                indicator = app.query_one("#prompt-file-indicator-1", Label)
                assert indicator.display is True
                assert "refactor_task.md" in str(indicator.content)

        asyncio.run(_run())

    def test_send_with_file_and_empty_composer_dispatches_file_pipeline(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "refactor_task.md"
                picked.write_text("Do the refactor", encoding="utf-8")
                app._slot_prompt_files[1] = str(picked)
                app.query_one("#composer-1", Input).value = ""

                app._execute_prompt_file_worker = MagicMock()
                app._execute_direct_worker = MagicMock()
                app._execute_attachment_worker = MagicMock()

                app._send_composer(1)

                app._execute_direct_worker.assert_not_called()
                app._execute_attachment_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_called_once()
                args = app._execute_prompt_file_worker.call_args[0]
                assert args[0] == 1  # slot
                assert args[1] == str(picked)  # prompt file path

        asyncio.run(_run())

    def test_send_with_file_and_typed_text_refuses_and_keeps_pick(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "refactor_task.md"
                picked.write_text("Do the refactor", encoding="utf-8")
                app._slot_prompt_files[1] = str(picked)
                app.query_one("#composer-1", Input).value = "Also type a task"

                app._execute_prompt_file_worker = MagicMock()
                app._execute_direct_worker = MagicMock()
                app._execute_attachment_worker = MagicMock()
                notices: list[str] = []
                app.notify = lambda msg, **kw: notices.append(str(msg))

                app._send_composer(1)

                app._execute_direct_worker.assert_not_called()
                app._execute_attachment_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_not_called()
                # Message must name a reachable remediation only.
                assert any("Clear the composer text" in n for n in notices), notices
                # Typed task stays so the operator can clear it.
                assert app.query_one("#composer-1", Input).value == "Also type a task"
                # Pick stays visible so the conflict remains on screen.
                assert app._slot_prompt_files[1] == str(picked)

        asyncio.run(_run())

    def test_send_with_attachment_and_prompt_file_refuses(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "task.md"
                picked.write_text("body", encoding="utf-8")
                folder = tmp_path / "docs"
                folder.mkdir()
                app._slot_prompt_files[1] = str(picked)
                app._slot_attachments[1] = str(folder)
                app.query_one("#composer-1", Input).value = ""

                app._execute_prompt_file_worker = MagicMock()
                app._execute_direct_worker = MagicMock()
                app._execute_attachment_worker = MagicMock()
                notices: list[str] = []
                app.notify = lambda msg, **kw: notices.append(str(msg))

                app._send_composer(1)

                app._execute_direct_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_not_called()
                app._execute_attachment_worker.assert_not_called()
                assert any("Clear the Attach-pill pick or the Prompt-pill file — not both." in n for n in notices), (
                    notices
                )
                # Both picks remain so the conflict stays visible.
                assert app._slot_prompt_files[1] == str(picked)
                assert app._slot_attachments[1] == str(folder)

        asyncio.run(_run())

    def test_send_with_typed_text_only_still_dispatches_direct_prompt(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app.query_one("#composer-1", Input).value = "Summarize this code"

                app._execute_prompt_file_worker = MagicMock()
                app._execute_direct_worker = MagicMock()
                app._execute_attachment_worker = MagicMock()

                app._send_composer(1)

                app._execute_prompt_file_worker.assert_not_called()
                app._execute_attachment_worker.assert_not_called()
                app._execute_direct_worker.assert_called_once()
                args = app._execute_direct_worker.call_args[0]
                assert args[0] == 1
                assert args[1] == "Summarize this code"

        asyncio.run(_run())

    def test_missing_prompt_file_drops_pick_and_errors(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                gone = tmp_path / "gone.md"
                app._slot_prompt_files[1] = str(gone)
                app.query_one("#composer-1", Input).value = ""

                app._execute_prompt_file_worker = MagicMock()
                app._execute_direct_worker = MagicMock()
                notices: list[str] = []
                app.notify = lambda msg, **kw: notices.append(str(msg))

                app._send_composer(1)

                app._execute_direct_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_not_called()
                assert 1 not in app._slot_prompt_files
                assert any("no longer exists" in n for n in notices)

        asyncio.run(_run())

    def test_empty_composer_and_no_file_warns(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app.query_one("#composer-1", Input).value = ""
                app._execute_direct_worker = MagicMock()
                app._execute_prompt_file_worker = MagicMock()
                notices: list[str] = []
                app.notify = lambda msg, **kw: notices.append(str(msg))

                app._send_composer(1)

                app._execute_direct_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_not_called()
                assert any("Type a task" in n for n in notices)

        asyncio.run(_run())

    def test_missing_prompt_capability_errors_without_dispatch(self, tmp_path: Path) -> None:
        app = make_app()
        app._prompt = None

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "task.md"
                picked.write_text("body", encoding="utf-8")
                app._slot_prompt_files[1] = str(picked)
                app.query_one("#composer-1", Input).value = ""

                app._execute_prompt_file_worker = MagicMock()
                notices: list[str] = []
                app.notify = lambda msg, **kw: notices.append(str(msg))

                app._send_composer(1)

                app._execute_prompt_file_worker.assert_not_called()
                assert any("capability is not available" in n for n in notices), notices

        asyncio.run(_run())

    def test_send_path_dispatches_process_prompt_file_only_verb(self, tmp_path: Path) -> None:
        """Drive real Send → real worker against a stub IPromptAggregate."""
        app = make_app(with_prompt_mock=True)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "task.md"
                picked.write_text("body", encoding="utf-8")
                app._slot_prompt_files[1] = str(picked)
                app.query_one("#composer-1", Input).value = ""
                _wire_sync_cft(app)

                app._send_composer(1)

                # Drain the worker the Send path spawned.
                worker = app._slot_workers.get(1)
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()

                app._prompt.execute.assert_called()
                req = app._prompt.execute.call_args[0][0]
                assert req.verb == "process_prompt_file_only"
                assert Path(str(req.prompt_file)) == picked

        asyncio.run(_run())

    def test_retry_rereads_pending_prompt_file(self, tmp_path: Path) -> None:
        """Issue 10: keyboard Run/Retry re-reads the pick without re-picking."""
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "task.md"
                picked.write_text("body", encoding="utf-8")
                app._slot_prompt_files[1] = str(picked)
                app._execute_prompt_file_worker = MagicMock()
                app._execute_slot_worker = MagicMock()

                app._run_slot(1)

                app._execute_slot_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_called_once()
                assert app._execute_prompt_file_worker.call_args[0][1] == str(picked)

        asyncio.run(_run())


class TestPromptFileWorkerFailures:
    def test_worker_exception_finalizes_failed(self, tmp_path: Path) -> None:
        app = make_app(with_prompt_mock=True)
        app._prompt.execute.side_effect = RuntimeError("browser exploded")

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "task.md"
                picked.write_text("body", encoding="utf-8")
                _wire_sync_cft(app)
                final: list[tuple] = []
                app._finalize_slot = lambda *a, **k: final.append(a)

                worker = app._execute_prompt_file_worker(1, str(picked), True)
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()

                assert final and final[0][1] == "FAILED"

        asyncio.run(_run())

    def test_worker_response_failure_finalizes_failed(self, tmp_path: Path) -> None:
        # R2-5: the detect_processing_failure FAILED branch must finalize the
        # slot FAILED with the failure marker as the reason.
        app = make_app(with_prompt_mock=True)
        # A response whose text is an error marker, not a raised exception.
        app._prompt.execute.return_value = MagicMock(response_text="ERROR [rate-limit] retry later")

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                picked = tmp_path / "task.md"
                picked.write_text("body", encoding="utf-8")
                _wire_sync_cft(app)
                final: list[tuple] = []
                app._finalize_slot = lambda *a, **k: final.append(a)

                worker = app._execute_prompt_file_worker(1, str(picked), True)
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()

                assert final and final[0][1] == "FAILED", final

        asyncio.run(_run())

    def test_worker_generation_guard_discards_stale_result(self, tmp_path: Path) -> None:
        # R2-3: drive the REAL _finalize_slot with a stale generation; the
        # guard must discard the stale result and leave slot state untouched.
        app = make_app(with_prompt_mock=True)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app._slot_generation[1] = 6  # current generation
                # Seed the slot as if a run is in progress.
                app._slot_stats[1] = {"status": "RUNNING", "file": "task.md", "duration": 0.0}
                app._slot_workers[1] = object()  # placeholder worker entry
                # Stale generation 5 captured by a worker that started earlier.
                app._finalize_slot(1, "SUCCESS", "task.md", 0.0, True, 5)

                # Guard discarded the stale result: stats untouched, worker entry preserved.
                assert app._slot_stats[1]["status"] == "RUNNING", app._slot_stats[1]
                assert app._slot_workers[1] is not None, app._slot_workers.get(1)

        asyncio.run(_run())


__all__ = ["TestPromptPillRouting", "TestPromptFileWorkerFailures"]
