"""Composer Send interaction tests (FE-5-02).

Cover the four Send paths through the real command path:

(a) typed text → Send → ``process_direct_prompt`` requested;
(b) empty composer with no file/attachment → warning, no dispatch;
(c) role label from ``modules/shared/templates/`` → template body dispatched;
(d) attachment set → attachment verb requested.

Assertions target the verb passed to a stubbed ``IPromptAggregate``.
Verb-level coverage for the prompt-file path lives in
``unit_tui_prompt_pill.py`` to avoid duplicating routing tests.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from unittest.mock import MagicMock

from textual.widgets import Button, Input
from textual.worker import WorkerFailed

from modules.shared.src.common.utility_core_prompt_template import load_prompt_template
from modules.tui.src.surface_tui_app_screen import QwenTuiApp
from modules.tui.tests.fixture_tui_app import make_app


def _wire_sync_cft(app: QwenTuiApp) -> None:
    def _cft(callback, *args, **kwargs):
        callback(*args, **kwargs)
        return None

    app.call_from_thread = _cft


class TestComposerDispatch:
    def test_typed_text_dispatches_direct_prompt(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                app.query_one("#composer-1", Input).value = "Summarize this PR"
                app._execute_direct_worker = MagicMock(return_value=None)
                app._execute_prompt_file_worker = MagicMock(return_value=None)
                app._execute_attachment_worker = MagicMock(return_value=None)

                # Issue 15: drive the Send button, not only _send_composer.
                app.query_one("#btn-send-1", Button).press()
                await pilot.pause(0.05)

                app._execute_direct_worker.assert_called_once()
                args = app._execute_direct_worker.call_args[0]
                assert args[1] == "Summarize this PR"
                app._execute_prompt_file_worker.assert_not_called()
                app._execute_attachment_worker.assert_not_called()

        asyncio.run(_run())

    def test_empty_composer_with_no_file_warns_without_dispatch(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app.query_one("#composer-1", Input).value = ""
                app._execute_direct_worker = MagicMock(return_value=None)
                app._execute_prompt_file_worker = MagicMock(return_value=None)
                app._execute_attachment_worker = MagicMock(return_value=None)
                notices: list[str] = []
                app.notify = lambda msg, **kw: notices.append(str(msg))

                app._send_composer(1)

                app._execute_direct_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_not_called()
                app._execute_attachment_worker.assert_not_called()
                assert any("Type a task" in n for n in notices)

        asyncio.run(_run())

    def test_role_label_dispatches_template_body(self) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                app.query_one("#composer-1", Input).value = "Frontend Engineer"
                captured: list[str] = []

                def _fake_direct(slot_id: int, prompt: str, headless: bool = True, out: str = "") -> None:
                    captured.append(prompt)

                def _noop(*args: object, **kwargs: object) -> None:
                    return None

                app._execute_direct_worker = _fake_direct
                app._execute_prompt_file_worker = _noop
                app._execute_attachment_worker = _noop

                app._send_composer(1)

                assert len(captured) == 1
                expected = load_prompt_template("frontend-engineer")
                assert captured[0] == expected
                assert captured[0] != "Frontend Engineer"

        asyncio.run(_run())

    def test_attachment_set_dispatches_attachment_verb(self, tmp_path: Path) -> None:
        app = make_app()

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                folder = tmp_path / "docs"
                folder.mkdir()
                app._slot_attachments[1] = str(folder)
                app.query_one("#composer-1", Input).value = "Audit the docs folder"

                app._execute_direct_worker = MagicMock(return_value=None)
                app._execute_prompt_file_worker = MagicMock(return_value=None)
                app._execute_attachment_worker = MagicMock(return_value=None)

                app._send_composer(1)

                app._execute_direct_worker.assert_not_called()
                app._execute_prompt_file_worker.assert_not_called()
                app._execute_attachment_worker.assert_called_once()
                args = app._execute_attachment_worker.call_args[0]
                assert args[0] == 1
                assert args[2] == str(folder)

        asyncio.run(_run())

    def test_direct_worker_requests_process_direct_prompt(self) -> None:
        app = make_app(with_prompt_mock=True)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                _wire_sync_cft(app)
                worker = app._execute_direct_worker(1, "Hello Qwen", True, "")
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()

                app._prompt.execute.assert_called_once()
                req = app._prompt.execute.call_args[0][0]
                assert req.verb == "process_direct_prompt"
                assert str(req.prompt) == "Hello Qwen"

        asyncio.run(_run())

    def test_attachment_worker_requests_process_prompt_with_attachment(self, tmp_path: Path) -> None:
        app = make_app(with_prompt_mock=True)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                prompt_path = app._write_prompt_temp_file(1, "Audit this")
                folder = tmp_path / "att"
                folder.mkdir()
                _wire_sync_cft(app)
                worker = app._execute_attachment_worker(1, prompt_path, str(folder), True, "")
                with contextlib.suppress(WorkerFailed):
                    if worker is not None:
                        await worker.wait()

                app._prompt.execute.assert_called_once()
                req = app._prompt.execute.call_args[0][0]
                assert req.verb == "process_prompt_with_attachment"
                assert Path(str(req.attachment_file)) == folder

        asyncio.run(_run())


__all__ = ["TestComposerDispatch"]
