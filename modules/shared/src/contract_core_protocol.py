"""Prompt-domain capability contracts (AES102 `_protocol`).

One file for the prompt feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IUploadProtocol``           → ``FileUploader``         (attachment upload, file validation)
- ``IFolderCompileProtocol``    → ``FolderCompiler``       (folder-to-markdown compilation)
- ``IFolderToAttachmentProtocol`` → ``FolderToAttachment`` (resolve folder to uploadable file)
- ``IInjectionProtocol``        → ``PromptInjector``       (multi-strategy DOM text injection)
- ``ISendProtocol``            → ``SendDispatcher``       (send action, message counting)
- ``IStreamProtocol``          → ``StreamMonitor``        (stable-response waiting, completeness)
- ``ISaverProtocol``           → ``OutputSaver``          (markdown persistence with metadata)

The other features carry their own contract files in
``modules/shared/src/``: ``contract_browser_protocol.py``,
``contract_config_protocol.py``, ``contract_jobs_protocol.py``,
``contract_logging_protocol.py``, ``contract_session_protocol.py``,
``contract_swarm_protocol.py``, ``contract_update_protocol.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import ElementHandle, Page

from modules.shared.src.taxonomy_core_constant import MAX_FOLDER_DEPTH, MAX_IMPORT_DEPTH
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_event import LifecycleEvent, QwenEventType
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    FileSizeBytes,
    HeadlessFlag,
    InjectorConfig,
    MaxFileSizeMb,
    MessageCount,
    MinTextLength,
    OutputChars,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
    StabilityChecks,
    TimeoutSec,
)

# A lifecycle observer receives every emitted pipeline event; surfaces use
# it to render event-level status (thinking / streaming / prompting) in the
# TUI slot badge and overview table.
LifecycleObserver = Callable[[QwenEventType, LifecycleEvent], None]


class IUploadProtocol(ABC):
    """File upload capability contract (external Qwen Web UI adaptation)."""

    @abstractmethod
    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        config: Any | None = None,
        emitter: LifecycleEmitter | None = None,
        web_loaded: HeadlessFlag = HeadlessFlag(True),
    ) -> bool:
        """Attach a file as an attachment. Returns True on success."""

    @abstractmethod
    def validate_file(self, filepath: Path, max_size_mb: MaxFileSizeMb = MaxFileSizeMb(100.0)) -> FileSizeBytes:
        """Pre-flight validation; returns file size in bytes."""


class IFolderCompileProtocol(ABC):
    """Folder-to-markdown compilation capability contract."""

    @abstractmethod
    def compile_folder(
        self,
        folder_path: Path,
        output_path: Path | None = None,
        max_depth: int = MAX_FOLDER_DEPTH,
        import_depth: int = MAX_IMPORT_DEPTH,
        include_imports: bool = True,
        boundary_root: Path | None = None,
    ) -> Path:
        """Compile folder contents to a single markdown file.

        Args:
            folder_path: Directory to compile.
            output_path: Optional output file path. Auto-generated if None.
            max_depth: Maximum recursion depth.
            import_depth: Maximum number of hops for resolving external
                imports/links beyond the first-hop files linked from the
                folder.  With the default of 1, only files linked directly
                from in-folder documents are included; transitive
                (second-hop) links are not followed.
            include_imports: Follow imports/links of folder files and include
                external dependencies (cycle-safe, bounded hops).
            boundary_root: Confinement boundary for import resolution.
                Resolved imports outside this root are refused because the
                compiled output is uploaded to a third-party service.
                Defaults to the ``QWEN_WORKSPACE_ROOT`` env var when set
                (matching the MCP workspace boundary), else the scanned
                folder's parent.

        Returns:
            Path to the compiled markdown file.
        """

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory (not a file)."""


class IFolderToAttachmentProtocol(ABC):
    """Folder-to-attachment resolution capability contract."""

    @abstractmethod
    def resolve_to_attachment(
        self,
        path: Path,
        max_depth: int = MAX_FOLDER_DEPTH,
        import_depth: int = MAX_IMPORT_DEPTH,
    ) -> Path:
        """Resolve a path to an attachment-ready file (compile folders to markdown)."""

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Check if path is a directory (not a file)."""


class IInjectionProtocol(ABC):
    """Prompt text injection capability contract."""

    @abstractmethod
    def find_input(self, page: Page, config: InjectorConfig | None = None) -> ElementHandle:
        """Locate the input element; raise if not found."""

    @abstractmethod
    def inject_text(self, page: Page, text: PromptText, config: InjectorConfig | None = None) -> None:
        """Inject prompt text via multi-strategy DOM injection."""


class ISendProtocol(ABC):
    """Send dispatcher capability contract."""

    @abstractmethod
    def click_send(
        self,
        page: Page,
        emitter: LifecycleEmitter,
        config: Any | None = None,
        document_parsed: HeadlessFlag = HeadlessFlag(True),
    ) -> None:
        """Trigger the send action."""

    @abstractmethod
    def count_messages(self, page: Page) -> MessageCount:
        """Count chat turns."""

    @abstractmethod
    def latest_message_text(self, page: Page) -> ResponseText | None:
        """Return the latest assistant response text."""


class IStreamProtocol(ABC):
    """Response streaming capability contract."""

    @abstractmethod
    def wait_for_response(
        self,
        page: Page,
        timeout_sec: TimeoutSec,
        msg_count_before: MessageCount,
        emitter: LifecycleEmitter,
        polling_interval_sec: PollIntervalSec = PollIntervalSec(1.0),
        stability_checks: StabilityChecks = StabilityChecks(4),
        min_text_length: MinTextLength = MinTextLength(1),
        dispatch_acknowledged: HeadlessFlag = HeadlessFlag(True),
        baseline_text: ResponseText | None = None,
        cancel_event: Any | None = None,
    ) -> ResponseText | None:
        """Wait for a stable assistant response; return its text.

        ``cancel_event`` is an optional per-run ``threading.Event``; when set
        the wait loop raises ``RunCancelledError`` instead of continuing to
        poll.
        """

    @abstractmethod
    def is_generation_complete(self, page: Page) -> bool:
        """True when Qwen has finished generating."""

    @abstractmethod
    def is_thinking_active(self, page: Page) -> bool:
        """True when Qwen is currently thinking/streaming."""


class ISaverProtocol(ABC):
    """Output persistence capability contract."""

    @abstractmethod
    def write_output(
        self,
        path: Path,
        content: ResponseText,
        ctx: RunContext,
        src: FilePath,
        dur: float,
        input_chars: int,
        output_chars: OutputChars,
        config: Any | None = None,
    ) -> None:
        """Write processed output with metadata header + sidecar."""


__all__ = [
    "IUploadProtocol",
    "IFolderCompileProtocol",
    "IFolderToAttachmentProtocol",
    "IInjectionProtocol",
    "ISendProtocol",
    "IStreamProtocol",
    "ISaverProtocol",
    "LifecycleObserver",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "IUploadProtocol": IUploadProtocol,
    "IFolderCompileProtocol": IFolderCompileProtocol,
    "IFolderToAttachmentProtocol": IFolderToAttachmentProtocol,
    "IInjectionProtocol": IInjectionProtocol,
    "ISendProtocol": ISendProtocol,
    "IStreamProtocol": IStreamProtocol,
    "ISaverProtocol": ISaverProtocol,
    "LifecycleObserver": LifecycleObserver,
}
