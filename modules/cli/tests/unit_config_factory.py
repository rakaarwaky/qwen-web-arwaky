"""Issue #280 AC-1: output-path filename uniqueness under concurrent slot runs.

The auto-naming contract in `modules/cli/FRD.md` FR-002.3 promises that
repeated runs never silently overwrite each other. A second-level timestamp
alone cannot satisfy that for two slot runs started in the same second, so
the resolved name also carries a 4-hex-digit suffix.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.common.taxonomy_core_constant import DIRECT_PROMPT_STEM
from modules.shared.src.config.utility_config_app_factory import resolve_pipeline_output_path


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


def test_explicit_output_file_path_is_honored_exactly(tmp_path: Path) -> None:
    """A user-supplied -o file path writes to that exact path, extension or not.

    Issue #280 AC-1 guarantees that *auto-generated* default filenames never
    collide under concurrent slot runs. When the operator explicitly names a
    destination with ``-o`` they own the collision risk: a path with an
    extension and a path without one are both honored in place, overwriting
    the file on a repeat run rather than being renamed.

    A directory argument still auto-completes inside it, because a directory
    cannot name a single file by itself.
    """
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# x", encoding="utf-8")

    # Extension path → exact file
    target_ext = tmp_path / "answer.md"
    target_ext.write_text("previous run", encoding="utf-8")
    _, out_path = resolve_pipeline_output_path(prompt, output_file=target_ext)
    assert out_path == target_ext

    # Extension-less path → exact file, no timestamp or hex suffix
    target_noext = tmp_path / "answer"
    _, out_path = resolve_pipeline_output_path(prompt, output_file=target_noext)
    assert out_path == target_noext
    assert out_path.parent == tmp_path


def test_directory_output_gets_a_unique_name_inside(tmp_path: Path) -> None:
    """A directory ``-o`` argument auto-completes a unique filename inside it.

    A directory cannot name a single file by itself, so the resolver
    appends the prompt stem, a timestamp, and a 4-hex-digit suffix to keep
    concurrent slot runs distinct within the operator's chosen folder.
    """
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# x", encoding="utf-8")
    out_dir = tmp_path / "out_dir"
    out_dir.mkdir()

    _, out_path = resolve_pipeline_output_path(prompt, output_file=out_dir)

    assert out_path.parent == out_dir
    assert out_path.suffix == ".md"
    assert out_path.name.startswith(f"{prompt.stem}_")
    assert len(out_path.stem.rsplit("_", 1)[-1]) == 4


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


def test_explicit_stem_overrides_prompt_stem_for_auto_names(tmp_path: Path) -> None:
    """Direct prompts pass DIRECT_PROMPT_STEM so tmpXXXX never names the output."""
    prompt = tmp_path / "tmpAb12Cd.txt"
    prompt.write_text("typed prompt", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _, out_path = resolve_pipeline_output_path(prompt, output_file=out_dir, stem=DIRECT_PROMPT_STEM)

    assert out_path.parent == out_dir
    assert out_path.name.startswith(f"{DIRECT_PROMPT_STEM}_")
    assert "tmpAb12Cd" not in out_path.name


def test_default_output_uses_direct_stem_when_no_output_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "modules.shared.src.config.utility_config_app_factory.DEFAULT_OUTPUT",
        tmp_path / "xdg-output",
    )
    prompt = tmp_path / "tmpZz99Yy.txt"
    prompt.write_text("typed prompt", encoding="utf-8")

    _, out_path = resolve_pipeline_output_path(prompt, stem=DIRECT_PROMPT_STEM)

    assert out_path.parent == tmp_path / "xdg-output"
    assert out_path.name.startswith(f"{DIRECT_PROMPT_STEM}_")
    assert "tmpZz99Yy" not in out_path.name
