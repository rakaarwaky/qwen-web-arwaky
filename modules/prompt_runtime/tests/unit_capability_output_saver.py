"""Tests for saver.py — remaining uncovered lines in strip_ui_noise, _write_text_file, write_output."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from modules.prompt_runtime.src.capabilities_output_saver import Saver
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

    def test_directory_destination_writes_one_file_per_concurrent_run(self, tmp_path):
        """BE-2-001: two runs in the same wall-clock second in the same
        directory must produce two distinct files, not one overwrite."""
        out_dir = tmp_path / "outputs"
        out_dir.mkdir()
        first_ctx = RunContext()
        second_ctx = RunContext()

        Saver().write_output(
            path=out_dir,
            content="first run answer",
            ctx=first_ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=6,
        )
        Saver().write_output(
            path=out_dir,
            content="second run answer",
            ctx=second_ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=7,
        )

        written = sorted(out_dir.glob("qwen_output_*.md"))
        assert len(written) == 2, f"two concurrent runs must write two files, got {written}"
        texts = {path.read_text() for path in written}
        assert texts == {"first run answer", "second run answer"}

    def test_directory_destination_name_carries_the_run_id(self, tmp_path):
        """The generated name must include the run id so a collision cannot
        happen by construction, not only by the existence check."""
        out_dir = tmp_path / "outputs"
        out_dir.mkdir()
        ctx = RunContext()

        Saver().write_output(
            path=out_dir,
            content="answer",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=1,
            output_chars=6,
        )

        written = list(out_dir.glob("qwen_output_*.md"))
        assert len(written) == 1
        assert str(ctx.run_id) in written[0].name

    def test_directory_destination_never_overwrites_an_existing_name(self, tmp_path):
        """A name already on disk must not be silently overwritten: the
        guard disambiguates instead, so the pre-existing content survives."""
        out_dir = tmp_path / "outputs"
        out_dir.mkdir()
        ctx = RunContext()
        taken = out_dir / f"qwen_output_20261022T000000_{ctx.run_id}.md"
        taken.write_text("already here")

        Saver().write_output(
            path=out_dir,
            content="answer",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=1,
            output_chars=6,
        )

        assert taken.read_text() == "already here", "an existing generated name must not be overwritten"
        new_files = [path for path in out_dir.glob("qwen_output_*.md") if path != taken]
        assert len(new_files) == 1
        assert new_files[0].read_text() == "answer"

    def test_an_explicitly_named_output_path_overwrites_in_place(self, tmp_path):
        """The operator named the destination, so an explicit path is
        honored exactly and repeated runs overwrite it (documented policy
        for BE-2-001: collision safety applies to generated names only)."""
        target = tmp_path / "named.md"
        ctx = RunContext()

        Saver().write_output(path=target, content="first", ctx=ctx, src="in.md", dur=0.1, input_chars=1, output_chars=5)
        Saver().write_output(
            path=target, content="second", ctx=ctx, src="in.md", dur=0.1, input_chars=1, output_chars=6
        )

        assert target.read_text() == "second"

    def test_atomic_write_enforces_owner_only_mode_under_any_umask(self, tmp_path, monkeypatch):
        """BE-2-002: the atomic branch must land 0o600 regardless of umask."""
        import os

        target = tmp_path / "atomic_mode.md"
        monkeypatch.setattr(os, "umask", lambda mask: 0o077)

        Saver()._write_text_file(target, "secret", atomic=True)

        mode = target.stat().st_mode & 0o777
        assert mode == 0o600, f"atomic write must pin 0o600, got {oct(mode)}"

    def test_atomic_write_enforces_owner_only_mode_with_a_lenient_umask(self, tmp_path, monkeypatch):
        """A default umask (0o022) must not leak group/other bits either."""
        import os

        target = tmp_path / "atomic_mode_lenient.md"
        monkeypatch.setattr(os, "umask", lambda mask: 0o022)

        Saver()._write_text_file(target, "secret", atomic=True)

        assert (target.stat().st_mode & 0o777) == 0o600

    def test_non_atomic_write_enforces_owner_only_mode(self, tmp_path):
        """The direct branch keeps its chmod guarantee (unchanged by BE-2-002)."""
        target = tmp_path / "direct_mode.md"

        Saver()._write_text_file(target, "secret", atomic=False)

        assert (target.stat().st_mode & 0o777) == 0o600

    def test_sidecar_failure_raises_after_the_main_file_is_written(self, tmp_path):
        """BE-2-003: a failed .meta.json is a hard error naming the sidecar,
        and the main response file stays on disk for inspection."""
        from unittest.mock import patch

        out_file = tmp_path / "result.md"
        ctx = RunContext()

        with patch(
            "modules.prompt_runtime.src.capabilities_output_saver.write_json_file",
            side_effect=OSError("disk full"),
        ):
            with pytest.raises(OutputWriteError, match=r"Failed to write output file .*meta\.json"):
                Saver().write_output(
                    path=out_file,
                    content="AI answer",
                    ctx=ctx,
                    src="in.md",
                    dur=0.1,
                    input_chars=2,
                    output_chars=9,
                )

        sidecar = out_file.with_suffix(".meta.json")
        assert out_file.is_file(), "the main artifact must survive a sidecar failure"
        assert out_file.read_text() == "AI answer"
        assert not sidecar.exists(), "the failed sidecar must not leave a partial file"

    def test_sidecar_failure_names_the_sidecar_path(self, tmp_path):
        """FR-PROMPT-009: the raised message names the sidecar path."""
        from unittest.mock import patch

        out_file = tmp_path / "named.md"
        sidecar = out_file.with_suffix(".meta.json")

        with patch(
            "modules.prompt_runtime.src.capabilities_output_saver.write_json_file",
            side_effect=OSError("quota exceeded"),
        ):
            with pytest.raises(OutputWriteError) as excinfo:
                Saver().write_output(
                    path=out_file,
                    content="AI answer",
                    ctx=RunContext(),
                    src="in.md",
                    dur=0.1,
                    input_chars=2,
                    output_chars=9,
                )

        assert str(sidecar) in str(excinfo.value)

    def test_atomic_sidecar_failure_is_rewrapped_naming_the_sidecar(self, tmp_path):
        """``atomic_write_text`` raises ``OutputWriteError`` (a QwenCliError,
        not an OSError); that type must be caught and re-wrapped with the
        sidecar path, not escape unwrapped."""
        from unittest.mock import patch

        out_file = tmp_path / "named.md"
        sidecar = out_file.with_suffix(".meta.json")

        with patch(
            "modules.prompt_runtime.src.capabilities_output_saver.write_json_file",
            side_effect=OutputWriteError(f"Atomic write failed for {sidecar}: disk full"),
        ):
            with pytest.raises(OutputWriteError) as excinfo:
                Saver().write_output(
                    path=out_file,
                    content="AI answer",
                    ctx=RunContext(),
                    src="in.md",
                    dur=0.1,
                    input_chars=2,
                    output_chars=9,
                )

        assert str(sidecar) in str(excinfo.value)
        assert out_file.is_file(), "the main artifact must survive a sidecar failure"

    def test_sidecar_ensure_dir_failure_is_rewrapped_naming_the_sidecar(self, tmp_path):
        """``ensure_dir`` sits inside the sidecar try, so an OSError creating
        the sidecar's parent directories is re-wrapped in the FR-PROMPT-009
        shape."""
        from unittest.mock import patch

        out_file = tmp_path / "named.md"
        sidecar = out_file.with_suffix(".meta.json")

        def _fail_sidecar_only(path):
            if str(path).endswith(".meta.json"):
                raise OSError("read-only filesystem")
            return ensure_dir(path)

        with patch(
            "modules.prompt_runtime.src.capabilities_output_saver.ensure_dir",
            side_effect=_fail_sidecar_only,
        ):
            with pytest.raises(OutputWriteError) as excinfo:
                Saver().write_output(
                    path=out_file,
                    content="AI answer",
                    ctx=RunContext(),
                    src="in.md",
                    dur=0.1,
                    input_chars=2,
                    output_chars=9,
                )

        assert str(sidecar) in str(excinfo.value)
        assert out_file.is_file(), "the main artifact must survive a sidecar failure"

    def test_unique_directory_path_reserves_the_candidate_exclusively(self, tmp_path):
        """The exclusive create pins the TOCTOU contract: the returned path
        already exists (reserved), so a second concurrent saver cannot claim
        the same name between the existence check and the write."""
        from unittest.mock import patch

        with patch(
            "modules.prompt_runtime.src.capabilities_output_saver.utc_now_iso",
            return_value="2026-01-01T00:00:00",
        ):
            first = Saver._unique_directory_path(tmp_path, "run1")
            assert first.exists(), "the exclusive create must reserve the candidate"
            second = Saver._unique_directory_path(tmp_path, "run1")
        assert second != first
        assert second.name.endswith("_1.md")
        assert second.exists()

    def test_unique_directory_path_skips_an_already_reserved_name(self, tmp_path):
        """A ``FileExistsError`` from the exclusive create moves to the next
        suffix instead of failing or reusing the name."""
        from unittest.mock import patch

        with patch(
            "modules.prompt_runtime.src.capabilities_output_saver.utc_now_iso",
            return_value="2026-01-01T00:00:00",
        ):
            reserved = tmp_path / "qwen_output_20260101T000000_run1.md"
            reserved.write_text("already here")
            candidate = Saver._unique_directory_path(tmp_path, "run1")

        assert candidate.name == "qwen_output_20260101T000000_run1_1.md"
        assert reserved.read_text() == "already here"

    def test_a_stalled_response_file_survives_a_mid_stream_extraction_failure(self, tmp_path):
        """FRD Test Scenario: a response file survives a mid-stream
        extraction failure. A verdict-bearing adapter that fails after the
        save must leave the artifact inspectable."""
        out_file = tmp_path / "survives.md"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt")
        error = OutputWriteError("extraction cut the stream")
        saver = MagicMock()
        saver.write_output.side_effect = error

        with pytest.raises(OutputWriteError):
            save_orchestrator_output(saver, out_file, prompt_file, "partial answer", 0.1, RunContext())

        saver.write_output.assert_called_once()

    def test_orchestrator_output_rejects_saver_without_file(self, tmp_path):
        out_file = tmp_path / "missing.md"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt")
        saver = MagicMock()

        with pytest.raises(OutputWriteError, match="readable file"):
            save_orchestrator_output(saver, out_file, prompt_file, "AI answer", 0.1, RunContext())
