"""Acceptance criteria for the prompt runtime capability door.

One test per FR-RUNTIME requirement in ``modules/prompt_runtime/FRD.md``:
the door refuses an unknown verb (FR-RUNTIME-006), persistence obeys the
artifact-permission and sidecar-location business rules
(FR-RUNTIME-005), and upload pre-flight rejects an over-ceiling file
(FR-RUNTIME-004). Real capability objects, real filesystem.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from modules.prompt_runtime.src.agent_prompt_runtime_orchestrator import PromptRuntimeOrchestrator
from modules.prompt_runtime.src.capabilities_file_uploader import FileUploader
from modules.prompt_runtime.src.capabilities_output_saver import Saver
from modules.prompt_runtime.src.capabilities_prompt_injector import PromptInjector
from modules.prompt_runtime.src.capabilities_send_dispatcher import SendDispatcher
from modules.prompt_runtime.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.common.taxonomy_core_error import QwenCliError
from modules.shared.src.common.taxonomy_core_vo import RunContext
from modules.shared.src.common.utility_io_writer import sidecar_path_for
from modules.shared.src.prompt_runtime.taxonomy_prompt_runtime_vo import RuntimeRequest


def _aggregate(tmp_path: Path) -> PromptRuntimeOrchestrator:
    return PromptRuntimeOrchestrator(
        injector=PromptInjector(),
        sender=SendDispatcher(),
        streamer=StreamMonitor(),
        uploader=FileUploader(),
        saver=Saver(metadata_dir=tmp_path / "meta"),
    )


def test_acceptance_a_verb_outside_the_runtime_set_is_refused(tmp_path: Path) -> None:
    """FR-RUNTIME-006: the aggregate door rejects a verb that none of the
    five capabilities serves, naming the verb in the error."""
    aggregate = _aggregate(tmp_path)

    with pytest.raises(QwenCliError, match="No prompt-runtime capability serves verb"):
        aggregate.execute(RuntimeRequest(verb="process_direct_prompt"))


def test_acceptance_a_persisted_artifact_is_private(tmp_path: Path) -> None:
    """FR-RUNTIME-005: written responses carry 0o600 so a response one
    operator wrote is never world-readable."""
    target = tmp_path / "answer.md"

    _aggregate(tmp_path).execute(
        RuntimeRequest(
            verb="persist",
            output_path=target,
            content="Private answer",
            ctx=RunContext(),
            dur=0.1,
            input_chars=5,
            output_chars=14,
        )
    )

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600, f"the response artifact must be owner read/write only, got {oct(mode)}"


def test_acceptance_the_sidecar_lands_in_the_metadata_dir_not_beside_the_output(tmp_path: Path) -> None:
    """FR-RUNTIME-005: run traceability lives under the metadata
    directory; the output directory holds only the response artifact."""
    target = tmp_path / "answer.md"
    meta_dir = tmp_path / "meta"

    _aggregate(tmp_path).execute(
        RuntimeRequest(
            verb="persist",
            output_path=target,
            content="Private answer",
            ctx=RunContext(),
            dur=0.1,
            input_chars=5,
            output_chars=14,
        )
    )

    sidecar = sidecar_path_for(target, meta_dir)
    assert sidecar.exists(), "the sidecar must be written under the metadata dir"
    assert not target.with_suffix(".meta.json").exists(), "the sidecar must not sit beside the artifact"


def test_acceptance_an_oversized_attachment_is_rejected_before_the_browser(tmp_path: Path) -> None:
    """FR-RUNTIME-004: the pre-flight ceiling is the exact 104857600-byte
    limit, so a file over it is rejected before any browser work starts."""
    from modules.shared.src.common.taxonomy_core_error import FileValidationError

    uploader = FileUploader()
    oversized = tmp_path / "over.md"
    oversized.write_bytes(b"0" * (104_857_600 + 1))

    with pytest.raises(FileValidationError, match="exceeds"):
        uploader.validate_file(oversized)


def test_acceptance_a_boundary_attachment_fits_the_ceiling(tmp_path: Path) -> None:
    """FR-RUNTIME-004: a file exactly at the ceiling still passes
    pre-flight; the limit rejects strictly-over sizes only."""
    uploader = FileUploader()
    boundary = tmp_path / "exact.md"
    boundary.write_bytes(b"0" * 104_857_600)

    assert uploader.validate_file(boundary) == 104_857_600
