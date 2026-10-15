"""Regression tests for the Attach pill (issue #341).

The Attach pill used to write its picked path into the slot's composer
Input. The composer is read as the *prompt source*, so an attached folder
was sent to `prompt file -i <folder>` instead of `prompt attach -a
<folder>` and the run failed. The pill must now store the path in the
app's per-slot attachment state and keep the composer prompt-only.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from textual.widgets import Input, Label

from modules.config.src.capabilities_config_slot_resolver import SlotRunPlanResolver
from modules.tui.src.surface_tui_app import QwenTuiApp
from modules.tui.src.surface_tui_navlog_handler import _attachment_label


def _make_app(tmp_path: Path) -> QwenTuiApp:
    return QwenTuiApp(
        workspace=MagicMock(),
        direct=MagicMock(),
        file_only=MagicMock(),
        attachment=MagicMock(),
        slot_config=SlotRunPlanResolver(),
        session=MagicMock(),
        jobs=MagicMock(),
    )


class TestAttachPillState:
    """The Attach pill keeps the composer prompt-only."""

    def test_attach_pill_stores_path_in_slot_state(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)) as pilot:
                folder = tmp_path / "project"
                folder.mkdir()

                app._open_attachment_picker(1)
                # Simulate the FilePickerModal dismissing with a folder path;
                # the dismiss callback lands on the next loop pass.
                picker = app.screen
                picker.dismiss(str(folder))
                for _ in range(5):
                    await pilot.pause(0.02)

                assert app._slot_attachments[1] == str(folder)
                # The composer stays empty: a path in it would become the
                # prompt source on the next run.
                assert app.query_one("#composer-1", Input).value == ""
                indicator = app.query_one("#file-indicator-1", Label)
                assert indicator.display is True
                assert "project" in str(indicator.content)

        asyncio.run(_run())

    def test_send_with_attachment_runs_attachment_pipeline(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                folder = tmp_path / "project"
                folder.mkdir()
                app._slot_attachments[1] = str(folder)
                app.query_one("#composer-1", Input).value = "Audit this code"

                # Mock the terminal executor so the real routing logic runs.
                app._execute_attachment_worker = MagicMock()
                app._execute_direct_worker = MagicMock()

                app._send_composer(1)

                # The attachment capability is used, not the direct prompt.
                app._execute_direct_worker.assert_not_called()
                app._execute_attachment_worker.assert_called_once()
                args = app._execute_attachment_worker.call_args[0]
                assert args[0] == 1  # slot
                assert args[2] == str(folder)  # attachment path
                # The typed task was written to a prompt file on disk.
                assert Path(args[1]).read_text(encoding="utf-8") == "Audit this code"
                # The composer is cleared after sending.
                assert app.query_one("#composer-1", Input).value == ""

        asyncio.run(_run())

    def test_attachment_worker_writes_prompt_file(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)

        prompt = app._write_prompt_temp_file(1, "Audit this code")
        assert prompt is not None
        assert prompt.suffix == ".md"
        assert prompt.read_text(encoding="utf-8") == "Audit this code"

    def test_run_slot_with_attachment_and_empty_composer_refuses(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                folder = tmp_path / "project"
                folder.mkdir()
                app._slot_attachments[1] = str(folder)
                # No typed task: the run must not start.
                app._run_composer_slot_with_attachment = MagicMock()
                app._execute_slot_worker = MagicMock()

                app._run_slot(1)

                app._run_composer_slot_with_attachment.assert_not_called()
                app._execute_slot_worker.assert_not_called()

        asyncio.run(_run())

    def test_run_slot_with_attachment_uses_attachment_pipeline(self, tmp_path: Path) -> None:
        app = _make_app(tmp_path)

        async def _run() -> None:
            async with app.run_test(size=(100, 40)):
                folder = tmp_path / "project"
                folder.mkdir()
                app._slot_attachments[1] = str(folder)
                app.query_one("#composer-1", Input).value = "Audit this code"

                app._run_composer_slot_with_attachment = MagicMock()
                app._execute_slot_worker = MagicMock()

                app._run_slot(1)

                app._execute_slot_worker.assert_not_called()
                app._run_composer_slot_with_attachment.assert_called_once()

        asyncio.run(_run())


class TestAttachmentLabel:
    """The file indicator distinguishes folders from typed files."""

    def test_folder_label(self, tmp_path: Path) -> None:
        folder = tmp_path / "service"
        folder.mkdir()
        assert _attachment_label(str(folder)) == "FOLDER: service"

    def test_supported_file_label(self, tmp_path: Path) -> None:
        f = tmp_path / "spec.pdf"
        f.write_text("x")
        assert _attachment_label(str(f)) == "<PDF> spec.pdf"

    def test_unsupported_file_label(self, tmp_path: Path) -> None:
        f = tmp_path / "blob.xyz"
        f.write_text("x")
        assert _attachment_label(str(f)) == "blob.xyz (unsupported type: xyz)"
