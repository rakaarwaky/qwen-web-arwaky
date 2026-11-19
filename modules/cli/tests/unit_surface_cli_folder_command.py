"""Unit tests for the folder CLI surface (surface_cli_folder_command)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.cli.src.surface_cli_folder_command import handle_folder_command
from modules.jobs.src.capabilities_folder_compiler import FolderCompiler
from modules.shared.src.common.taxonomy_core_error import (
    FolderCompileError,
    FolderDepthExceededError,
    FolderEmptyError,
    FolderValidationError,
)


def _folder_args(folder_path: str | None) -> argparse.Namespace:
    args = argparse.Namespace()
    args.folder_path = folder_path
    return args


class TestFolderCompile:
    def test_compile_tmp_folder(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Compiling a real folder writes a markdown file and returns 0."""
        (tmp_path / "a.md").write_text("# A", encoding="utf-8")
        (tmp_path / "b.md").write_text("# B", encoding="utf-8")
        compiler = FolderCompiler(input_dir=tmp_path / "out")

        rc = handle_folder_command(_folder_args(str(tmp_path)), compiler)

        assert rc == 0
        out_dir = tmp_path / "out"
        assert out_dir.is_dir()
        produced = list(out_dir.glob("*.md"))
        assert len(produced) == 1
        out = capsys.readouterr().out
        assert str(produced[0]) in out
        assert "Compiled" in out

    def test_compile_default_output_under_dot_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without an explicit input_dir the compiler defaults to .qwen-web-arwaky/input/."""
        (tmp_path / "a.md").write_text("# A", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        compiler = FolderCompiler()

        rc = handle_folder_command(_folder_args(str(tmp_path)), compiler)

        assert rc == 0
        expected_dir = tmp_path / ".qwen-web-arwaky" / "input"
        assert expected_dir.is_dir()
        produced = list(expected_dir.glob("*.md"))
        assert len(produced) == 1
        assert str(produced[0]) in capsys.readouterr().out

    def test_compile_empty_folder_returns_error(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty folder triggers FolderEmptyError from the capability layer."""
        empty_folder = tmp_path / "empty"
        empty_folder.mkdir()
        compiler = FolderCompiler(input_dir=tmp_path / "out")

        rc = handle_folder_command(_folder_args(str(empty_folder)), compiler)

        assert rc == 1
        err = capsys.readouterr().err
        assert "[ERROR]" in err
        assert "No compilable files" in err

    def test_reject_file_not_folder(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A file path is rejected with returncode 1 and a stderr message."""
        target = tmp_path / "file.md"
        target.write_text("# hi", encoding="utf-8")
        compiler = FolderCompiler(input_dir=tmp_path / "out")

        rc = handle_folder_command(_folder_args(str(target)), compiler)

        assert rc == 1
        err = capsys.readouterr().err
        assert "Path is not a directory" in err

    def test_reject_missing_path(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A non-existent path is rejected with returncode 1 and a stderr message."""
        missing = tmp_path / "does_not_exist"
        compiler = FolderCompiler(input_dir=tmp_path / "out")

        rc = handle_folder_command(_folder_args(str(missing)), compiler)

        assert rc == 1
        err = capsys.readouterr().err
        assert "Folder does not exist" in err

    def test_missing_folder_path_prints_usage_hint(self, capsys: pytest.CaptureFixture[str]) -> None:
        """No ``folder_path`` returns 1 with a usage hint on stderr."""
        compiler = FolderCompiler(input_dir=Path("/tmp/out"))

        rc = handle_folder_command(_folder_args(None), compiler)

        assert rc == 1
        err = capsys.readouterr().err
        assert "Missing folder path" in err
        assert "qwen-web-arwaky folder <path>" in err

    @pytest.mark.parametrize(
        "exc",
        [
            FolderValidationError("bad folder"),
            FolderEmptyError("no compilable files"),
            FolderCompileError("disk full"),
            FolderDepthExceededError("depth exceeded"),
        ],
    )
    def test_compile_errors_print_error_line(
        self, tmp_path: Path, exc: Exception, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Compile errors from the capability surface as a single [ERROR] line and return 1."""
        compiler = MagicMock()
        compiler.compile_folder.side_effect = exc

        rc = handle_folder_command(_folder_args(str(tmp_path)), compiler)

        assert rc == 1
        err = capsys.readouterr().err
        assert "[ERROR]" in err
        assert str(exc) in err
