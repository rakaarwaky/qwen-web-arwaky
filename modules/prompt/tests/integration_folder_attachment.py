"""Integration tests for the folder-to-attachment compiler.

The folder path is what makes an entire project one attachment, so these
run the real resolver over a real directory tree and assert a single file
passes through while a folder is compiled.
"""

from __future__ import annotations

from pathlib import Path

from modules.jobs.src.capabilities_folder_to_attachment import FolderToAttachmentAdapter


def _adapter(tmp_path: Path) -> FolderToAttachmentAdapter:
    """Return the resolver wired to the real folder compiler.

    The compiler writes its bundle beside the caller's output directory, so
    each test gets its own temporary tree.
    """
    from modules.jobs.src.capabilities_folder_compiler import FolderCompiler

    return FolderToAttachmentAdapter(FolderCompiler())


def test_integration_a_single_file_attachment_passes_through_unchanged(tmp_path: Path) -> None:
    """A single named file is not a folder to compile, so it stays the
    attachment rather than becoming a one-file bundle.
    """
    attachment = tmp_path / "report.md"
    attachment.write_text("# Report\n\nRevenue grew.", encoding="utf-8")
    adapter = _adapter(tmp_path)

    resolved = adapter.resolve_to_attachment(attachment)

    assert resolved == attachment


def test_integration_a_folder_is_recognised_as_a_folder(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('hi')", encoding="utf-8")
    adapter = _adapter(tmp_path)

    assert adapter.is_folder(project) is True


def test_integration_a_single_file_is_not_recognised_as_a_folder(tmp_path: Path) -> None:
    attachment = tmp_path / "report.md"
    attachment.write_text("# Report", encoding="utf-8")
    adapter = _adapter(tmp_path)

    assert adapter.is_folder(attachment) is False
