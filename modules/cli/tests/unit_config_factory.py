"""Issue #280 AC-1: output-path filename uniqueness under concurrent slot runs.

The auto-naming contract in `modules/cli/FRD.md` FR-002.3 promises that
repeated runs never silently overwrite each other. A second-level timestamp
alone cannot satisfy that for two slot runs started in the same second, so
the resolved name also carries a 4-hex-digit suffix.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.utility_config_app_factory import resolve_pipeline_output_path


def test_directory_output_names_are_unique_across_rapid_calls(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# x", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    first, first_out = resolve_pipeline_output_path(prompt, output_file=out_dir)
    second, second_out = resolve_pipeline_output_path(prompt, output_file=out_dir)

    assert first == second == prompt
    assert first_out != second_out
    assert first_out.suffix == second_out.suffix == ".md"
    # {stem}_{YYYYMMDD-HHMMSS}_{hex4}
    assert first_out.name.startswith(f"{prompt.stem}_")
    assert len(first_out.stem.rsplit("_", 1)[-1]) == 4


def test_explicit_output_file_path_is_honored_in_place(tmp_path: Path) -> None:
    """A user-supplied -o file path (with an extension) writes to that exact path.

    Issue #280 AC-1 guarantees *default* filenames never collide, but an
    explicit ``-o`` argument names the destination the operator wants, so it
    is honored exactly (overwritten on a repeat run) rather than renamed.
    """
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# x", encoding="utf-8")
    target = tmp_path / "answer.md"
    target.write_text("previous run", encoding="utf-8")

    _, out_path = resolve_pipeline_output_path(prompt, output_file=target)

    assert out_path == target
    assert out_path.parent == tmp_path


def test_explicit_extensionless_output_path_gets_a_unique_name(tmp_path: Path) -> None:
    """An explicit -o path without an extension still auto-completes the name.

    A directory-like or extensionless argument is not a precise file target,
    so a timestamp + hex suffix is appended to keep concurrent runs distinct.
    """
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# x", encoding="utf-8")
    target = tmp_path / "answer"

    _, out_path = resolve_pipeline_output_path(prompt, output_file=target)

    assert out_path != target
    assert out_path.parent == tmp_path
    assert out_path.stem.startswith("answer_")


def test_unicode_and_space_containing_stems_survive_resolution(tmp_path: Path) -> None:
    """AC-4: no truncation and no encoding substitution in the stem."""
    prompt = tmp_path / "prompt file \u00e9\u00e0 \u4f60\u597d.md"
    prompt.write_text("# x", encoding="utf-8")
    out_dir = tmp_path / "out dir"
    out_dir.mkdir()

    _, out_path = resolve_pipeline_output_path(prompt, output_file=out_dir, attachment_path=prompt)

    assert out_path.parent == out_dir
    assert prompt.stem in out_path.name
    assert "\u4f60\u597d" in out_path.name
