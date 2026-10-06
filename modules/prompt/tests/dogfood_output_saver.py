"""Dogfood tests for the output saver against a real filesystem.

These save real responses under a temporary directory, so the response
file, the sidecar metadata, and the atomic-write path are exercised
against the filesystem rather than a stub.
"""

from __future__ import annotations

import json
from pathlib import Path

from modules.prompt.src.capabilities_output_saver import Saver
from modules.shared.src.taxonomy_core_vo import RunContext


def _save(saver: Saver, target: Path, source: Path, context: RunContext) -> None:
    saver.write_output(
        path=target,
        content="The summary",
        ctx=context,
        src=source,
        dur=1.5,
        input_chars=len("Summarize this"),
        output_chars=len("The summary"),
    )


def test_dogfood_a_saved_response_lands_at_the_named_path(tmp_path: Path) -> None:
    source = tmp_path / "prompt.md"
    source.write_text("Summarize this", encoding="utf-8")
    target = tmp_path / "answer.md"

    _save(Saver(), target, source, RunContext())

    assert target.exists()
    assert "The summary" in target.read_text(encoding="utf-8")


def test_dogfood_a_saved_response_carries_its_run_metadata(tmp_path: Path) -> None:
    """The sidecar is what a monitor reads to report progress, so it must
    name the run it belongs to.
    """
    source = tmp_path / "prompt.md"
    source.write_text("Summarize this", encoding="utf-8")
    target = tmp_path / "answer.md"
    context = RunContext()

    _save(Saver(), target, source, context)

    sidecar = target.with_suffix(".meta.json")
    assert sidecar.exists(), "a saved response must carry the metadata a monitor reads"
    assert context.run_id in sidecar.read_text(encoding="utf-8")


def test_dogfood_the_sidecar_is_valid_json(tmp_path: Path) -> None:
    source = tmp_path / "prompt.md"
    source.write_text("Summarize this", encoding="utf-8")
    target = tmp_path / "answer.md"

    _save(Saver(), target, source, RunContext())

    sidecar = json.loads(target.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert isinstance(sidecar, dict)


def test_dogfood_overwriting_a_response_leaves_no_partial_file(tmp_path: Path) -> None:
    """The write is atomic, so a reader never sees a half-written answer."""
    source = tmp_path / "prompt.md"
    source.write_text("Summarize this", encoding="utf-8")
    target = tmp_path / "answer.md"
    saver = Saver()

    _save(saver, target, source, RunContext())
    _save(saver, target, source, RunContext())

    assert "The summary" in target.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*.tmp")), "an atomic write must not leave a temporary file behind"
