"""Capabilities: file saver (AES403).

Implements ISaverProtocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.shared.src.common.taxonomy_core_constant import (
    DEFAULT_ATOMIC_WRITE,
    DEFAULT_GENERATE_SIDECAR,
    DEFAULT_METADATA_DIR,
)
from modules.shared.src.common.taxonomy_core_error import OutputWriteError
from modules.shared.src.common.taxonomy_core_vo import (
    AtomicWriteFlag,
    FilePath,
    GenerateSidecarFlag,
    OutputChars,
    ResponseText,
    RunContext,
)
from modules.shared.src.common.utility_core_text import strip_ui_noise, utc_now_iso
from modules.shared.src.common.utility_io_writer import (
    atomic_write_text,
    ensure_dir,
    sidecar_path_for,
    write_json_file,
)
from modules.shared.src.common.utility_logger_factory import get_logger
from modules.shared.src.prompt.contract_prompt_protocol import ISaverProtocol

log = get_logger("capabilities_saver")


class Saver(ISaverProtocol):
    """Atomic file writer with metadata traceability header and JSON sidecar.

    Directory destinations get a generated filename that carries the run id
    and refuses to reuse a name already on disk, so two slot workers that
    land in the same wall-clock second never overwrite each other's output
    (issue #280 concurrency follow-up). An explicitly named file is honored
    exactly as the operator named it and overwrites in place — the operator
    picked the destination, so collision safety there is the operator's
    choice.
    """

    def __init__(
        self,
        generate_sidecar: GenerateSidecarFlag = GenerateSidecarFlag(DEFAULT_GENERATE_SIDECAR),
        atomic_write: AtomicWriteFlag = AtomicWriteFlag(DEFAULT_ATOMIC_WRITE),
        metadata_dir: Path | None = None,
    ) -> None:
        self.generate_sidecar = generate_sidecar
        self.atomic_write = atomic_write
        self.metadata_dir = metadata_dir if metadata_dir is not None else DEFAULT_METADATA_DIR

    def write_output(
        self,
        path: Path,
        content: ResponseText | str,
        ctx: RunContext,
        src: FilePath | str,
        dur: float,
        input_chars: int,
        output_chars: OutputChars | int,
        config: Any | None = None,
    ) -> None:
        """Write processed output to disk with a JSON sidecar file:

        Step 1: Resolve configuration & metadata
        Step 2: Ensure destination parent directory
        Step 3: Write main content file (atomic or direct)
        Step 4: Generate .meta.json sidecar file
        """
        # Step 1: Resolve configuration & metadata
        cfg = config or {}
        if not isinstance(cfg, dict):
            cfg = {
                "generate_sidecar": getattr(cfg, "generate_sidecar", self.generate_sidecar),
                "atomic_write": getattr(cfg, "atomic_write", self.atomic_write),
            }
        generate_sidecar = cfg.get("generate_sidecar", self.generate_sidecar)
        atomic_write = cfg.get("atomic_write", self.atomic_write)
        run_id = str(ctx.run_id)
        iso_timestamp = utc_now_iso()

        full_text = strip_ui_noise(content)

        # Step 2: Ensure destination parent directory
        try:
            if path.is_dir():
                path = self._unique_directory_path(path, run_id)
            ensure_dir(path)
        except OSError as e:
            log.error("Failed to create parent dirs for %s (I/O error): %s", path, e)
            raise OutputWriteError(f"Failed to write output file {path}: {e}") from e

        # Step 3: Write main content file (atomic or direct). A write failure
        # after an exclusive name reservation leaves a zero-byte husk
        # behind, so the reserved candidate is unlinked when it still has no
        # content.
        write_error: OutputWriteError | None = None
        try:
            self._write_text_file(path, full_text, atomic_write)
        except OutputWriteError as e:
            write_error = e
            self._release_reserved_name(path)
        if write_error is not None:
            raise write_error

        # Step 4: Generate .meta.json sidecar under the XDG meta root (if enabled)
        if generate_sidecar:
            # The sidecar is mandatory traceability (FR-PROMPT-009): the run
            # is not reportable as written when its provenance is missing,
            # so a failure here raises after the main file is safely on
            # disk — the artifact stays inspectable either way.
            sidecar_path = sidecar_path_for(path, self.metadata_dir)
            try:
                ensure_dir(sidecar_path)
                meta_dict = {
                    "run_id": run_id,
                    "source_file": str(src),
                    "processed_at": iso_timestamp,
                    "duration_sec": round(dur, 2),
                    "input_chars": int(input_chars),
                    "output_chars": int(output_chars),
                }
                write_json_file(sidecar_path, meta_dict, atomic=bool(atomic_write))
            except (OSError, TypeError, ValueError, OutputWriteError) as e:
                log.error("Failed to write metadata sidecar for %s: %s", sidecar_path, e)
                raise OutputWriteError(f"Failed to write output file {sidecar_path}: {e}") from e

        log.info("output_file_written: %s", path.name)

    @staticmethod
    def _unique_directory_path(directory: Path, run_id: str) -> Path:
        """Name a response file inside *directory* that cannot collide.
        The name carries the run id — unique per run by construction — plus
        a UTC timestamp, and each candidate is reserved with an exclusive
        create (``touch(exist_ok=False)``) so two concurrent savers that
        interleave between the existence check and the write surface a hard
        ``FileExistsError`` on the loser (handled by moving to the next
        suffix) instead of a silent overwrite. The timestamp is UTC so the
        name and the ``processed_at`` sidecar field agree on one clock.
        """
        base = f"qwen_output_{utc_now_iso().replace(':', '').replace('-', '')}_{run_id}"
        counter = 0
        while True:
            suffix = f"_{counter}" if counter else ""
            candidate = directory / f"{base}{suffix}.md"
            try:
                candidate.touch(exist_ok=False)
            except FileExistsError:
                counter += 1
                continue
            return candidate

    @staticmethod
    def _release_reserved_name(path: Path) -> None:
        """Unlink a reserved candidate that still has no content.

        The exclusive create in :meth:`_unique_directory_path` claims the
        name before the write; when the write fails the zero-byte husk is
        removed so a later attempt in the same directory does not take the
        next suffix for no reason.
        """
        try:
            if path.exists() and path.stat().st_size == 0:
                path.unlink()
        except OSError:
            log.debug("Could not unlink reserved candidate %s", path)

    def _write_text_file(self, path: Path, content: str, atomic: bool) -> None:
        """Write *content* to *path*, atomically or directly.

        Enforces 0o600 permissions for output artifact confidentiality (Issue #353).
        ``atomic_write_text`` pins the mode on the temp file before the
        rename and re-asserts it on the destination, so the atomic path is
        covered as well; the direct path pins it after the write.

        Raises
        ------
        OutputWriteError
            When an I/O error occurs on the write path.
        """
        if atomic:
            atomic_write_text(path, content)
            return
        try:
            path.write_text(content, encoding="utf-8")
            path.chmod(0o600)
        except OSError as e:
            log.error("Failed to write output file %s (I/O error): %s", path, e)
            raise OutputWriteError(f"Failed to write output file {path}: {e}") from e

    def __repr__(self) -> str:
        """Return string representation of Saver."""
        return f"Saver(sidecar={self.generate_sidecar}, atomic={self.atomic_write})"
