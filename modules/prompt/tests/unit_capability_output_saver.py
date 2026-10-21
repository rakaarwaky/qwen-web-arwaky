"""Tests for saver.py — remaining uncovered lines in strip_ui_noise, _write_text_file, write_output."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from modules.prompt.src.capabilities_output_saver import Saver
from modules.shared.src import RunContext, SaverConfig
from modules.shared.src.common.taxonomy_core_error import OutputWriteError
from modules.shared.src.common.utility_core_text import strip_ui_noise
from modules.shared.src.common.utility_io_writer import ensure_dir, save_orchestrator_output, sidecar_path_for


class TestStripUiNoise:
    def test_strips_qwen_model_names(self):
        text = "Qwen3\nQwen3.8-Max\nActual content here"
        result = strip_ui_noise(text)
        assert "Qwen3" not in result
        assert "Actual content here" in result

    def test_strips_question_mark(self):
        text = "?\nReal answer"
        result = strip_ui_noise(text)
        assert result == "Real answer"

    def test_strips_file_size_suffixes(self):
        text = "12.5 KB\nDocument.docx\nReal content"
        result = strip_ui_noise(text)
        assert "12.5 KB" not in result

    def test_no_stripping_needed(self):
        text = "# Heading\nSome content"
        result = strip_ui_noise(text)
        assert result == text

    def test_all_noise_returns_original(self):
        text = "Qwen3\nQwen Plus\nAuto"
        result = strip_ui_noise(text)
        assert result == text

    def test_blank_lines_before_content(self):
        text = "\n\n\nReal content"
        result = strip_ui_noise(text)
        assert "Real content" in result

    def test_empty_string(self):
        assert strip_ui_noise("") == ""


class TestWriteFileAtomic:
    def test_atomic_write(self, tmp_path):
        target = tmp_path / "output.md"
        Saver()._write_text_file(target, "hello world", atomic=True)
        assert target.read_text() == "hello world"

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "sub" / "dir" / "file.md"
        ensure_dir(target)
        Saver()._write_text_file(target, "nested", atomic=True)
        assert target.read_text() == "nested"


class TestSidecarPathFor:
    def test_under_default_output_mirrors_relative_path(self, tmp_path, monkeypatch):
        default_output = tmp_path / "xdg-output"
        nested = default_output / "nested"
        nested.mkdir(parents=True)
        out_file = nested / "result.md"
        meta_dir = tmp_path / "meta"
        monkeypatch.setattr(
            "modules.shared.src.common.utility_io_writer.DEFAULT_OUTPUT",
            default_output,
        )
        sidecar = sidecar_path_for(out_file, meta_dir)
        assert sidecar == meta_dir.resolve() / "nested" / "result.meta.json"
        assert sidecar.parent != out_file.parent

    def test_absolute_path_outside_default_output_nests_under_meta(self, tmp_path):
        out_file = tmp_path / "custom" / "answer.md"
        meta_dir = tmp_path / "meta"
        sidecar = sidecar_path_for(out_file, meta_dir)
        assert sidecar.suffix == ".json"
        assert sidecar.name == "answer.meta.json"
        assert meta_dir.resolve() in sidecar.parents
        assert sidecar.parent != out_file.parent


class TestWriteOutputExtended:
    def test_with_sidecar(self, tmp_path):
        out_file = tmp_path / "result.md"
        meta_dir = tmp_path / "meta"
        ctx = RunContext()
        Saver(metadata_dir=meta_dir).write_output(
            path=out_file,
            content="AI answer",
            ctx=ctx,
            src="input.md",
            dur=1.0,
            input_chars=5,
            output_chars=9,
        )
        sidecar = sidecar_path_for(out_file, meta_dir)
        assert sidecar.exists()
        assert not out_file.with_suffix(".meta.json").exists()
        meta = json.loads(sidecar.read_text())
        assert meta["run_id"] == ctx.run_id

    def test_without_sidecar(self, tmp_path):
        out_file = tmp_path / "plain.md"
        ctx = RunContext()
        cfg = SaverConfig(generate_sidecar=False)
        meta_dir = tmp_path / "meta"
        Saver(metadata_dir=meta_dir).write_output(
            path=out_file,
            content="plain",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=5,
            config=cfg,
        )
        assert not sidecar_path_for(out_file, meta_dir).exists()

    def test_non_atomic_write(self, tmp_path):
        out_file = tmp_path / "result.md"
        ctx = RunContext()
        cfg = SaverConfig(atomic_write=False)
        Saver().write_output(
            path=out_file,
            content="data",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=4,
            config=cfg,
        )
        assert out_file.exists()

    def test_strips_ui_noise(self, tmp_path):
        out_file = tmp_path / "result.md"
        ctx = RunContext()
        Saver().write_output(
            path=out_file,
            content="Qwen3\nReal content here",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=20,
        )
        content = out_file.read_text()
        assert "Qwen3" not in content
        assert "Real content here" in content

    def test_orchestrator_output_emits_terminal_event_after_file_write(self, tmp_path):
        out_file = tmp_path / "result.md"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt")
        emitter = MagicMock()

        save_orchestrator_output(Saver(), out_file, prompt_file, "AI answer", 0.1, RunContext(), emitter=emitter)

        assert out_file.is_file()
        assert out_file.read_text()
        emitter.emit.assert_called_once()
        assert str(emitter.emit.call_args.args[0]) == "EVENT_OUTPUT_COPIED"

    def test_orchestrator_output_rejects_saver_without_file(self, tmp_path):
        out_file = tmp_path / "missing.md"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt")
        saver = MagicMock()

        with pytest.raises(OutputWriteError, match="readable file"):
            save_orchestrator_output(saver, out_file, prompt_file, "AI answer", 0.1, RunContext())
