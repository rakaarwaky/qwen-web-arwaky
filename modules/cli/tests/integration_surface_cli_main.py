"""Integration tests for the CLI entry point — folder compile dispatch.

Drives ``modules.root_cli_main_entry.main(argv=...)`` end-to-end for the
``folder`` verb, asserting the exit code and that a Markdown file is produced
under ``.qwen-web-arwaky/input/``. Also covers the argparse boundary cases
and the missing-path usage hint.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import modules.root_cli_main_entry as root_entry


@pytest.fixture
def tmp_folder(tmp_path: Path) -> Path:
    """A folder with two Markdown files."""
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "a.md").write_text("# A", encoding="utf-8")
    (folder / "b.md").write_text("# B", encoding="utf-8")
    return folder


@pytest.fixture
def tmp_file(tmp_path: Path) -> Path:
    """A regular file (not a folder)."""
    target = tmp_path / "file.md"
    target.write_text("# hi", encoding="utf-8")
    return target


class TestFolderCompileIntegration:
    def test_folder_exits_zero_and_writes_output(
        self, tmp_folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        rc = root_entry.main(["folder", str(tmp_folder)])
        assert rc == 0
        expected_dir = tmp_path / ".qwen-web-arwaky" / "input"
        assert expected_dir.is_dir()
        produced = list(expected_dir.glob("*.md"))
        assert len(produced) == 1
        out = capsys.readouterr().out
        assert str(produced[0]) in out

    def test_folder_on_file_exits_nonzero(self, tmp_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = root_entry.main(["folder", str(tmp_file)])
        assert rc == 1
        err = capsys.readouterr().err
        assert "Path is not a directory" in err
        assert "[ERROR]" in err

    def test_folder_no_path_exits_2(self) -> None:
        """`folder` without a path exits 2 (argparse rejects missing required arg)."""
        with pytest.raises(SystemExit) as excinfo:
            root_entry.main(["folder"])
        assert excinfo.value.code == 2

    def test_folder_argparse_extra_positional_exits_2(self) -> None:
        """Extra positional after the path exits 2."""
        with pytest.raises(SystemExit) as excinfo:
            root_entry.main(["folder", "a", "b"])
        assert excinfo.value.code == 2
