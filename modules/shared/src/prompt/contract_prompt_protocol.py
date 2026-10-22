"""Prompt-domain capability contracts (AES102 `_protocol`).

One file for the prompt feature. Each class below is one capability
seam: a class carries every method that capability implements, with one
concrete return type each, so a capability implements its class outright
and never carries stubs.

Seams:

- ``IDirectPromptProtocol``     → ``DirectPromptAdapter``
- ``IPromptFileProtocol``       → ``PromptFileAdapter``
- ``IAttachmentPromptProtocol`` → ``AttachmentPromptAdapter``
- ``IPromptFlowProtocol``       → ``PromptFlowDispatcher``
- ``IRunCancelProtocol``        → ``RunCancelRegistry``  (targeted browser-context cancel)

The outward entry point, ``IPromptAggregate``, is in
``contract_prompt_aggregate.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import ElementHandle, Page

from modules.shared.src.common.taxonomy_core_constant import MAX_FOLDER_DEPTH, MAX_IMPORT_DEPTH
from modules.shared.src.common.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.common.taxonomy_core_event import LifecycleEvent, QwenEventType
from modules.shared.src.common.taxonomy_core_vo import (
    AppConfig,
    AttachmentPath,
    CancelToken,
    FilePath,
    FileSizeBytes,
    HeadlessFlag,
    InjectorConfig,
    MaxFileSizeBytes,
    MessageCount,
    MinTextLength,
    OutputChars,
    OutputPath,
    PollIntervalSec,
    PromptPath,
    PromptText,
    ResponseText,
    RunContext,
    RunId,
    RunState,
    SenderConfig,
    StabilityChecks,
    TimeoutSec,
)
from modules.shared.src.logging.contract_logging_protocol import IObservabilityProtocol
from modules.shared.src.prompt.taxonomy_prompt_vo import PromptRequest, PromptResponse, StreamVerdict


class IDirectPromptProtocol(ABC):
    """Direct text-prompt capability: inject, send, and collect one answer."""

    @abstractmethod
    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run the prompt verb this capability serves; return its response."""
        ...

    @abstractmethod
    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec | int = 120,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        event_observer: LifecycleObserver | None = None,
        session_resolver: Callable[[], Path | None] | None = None,
    ) -> PromptResponse:
        """Process a direct text prompt string.

        ``event_observer`` optionally receives every emitted lifecycle event
        so a surface can render event-level status (thinking / streaming /
        prompting) for the run.

        ``session_resolver`` optionally returns the session pool path chosen
        by session rotation for this run. The prompt pipeline itself builds
        its own AppConfig, so without the resolver a pool selection made
        upstream by the surface is silently dropped and the default session
        is used instead. A resolver that raises reports no session and is
        swallowed; an empty pool must resolve the logged-in profile.
        """
        ...


class IPromptFileProtocol(ABC):
    """Prompt-file capability: read a Markdown file, run it, persist the answer."""

    @abstractmethod
    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run the prompt verb this capability serves; return its response."""
        ...

    @abstractmethod
    def process_prompt_file_only(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        cancel_event: CancelToken | None = None,
        event_observer: LifecycleObserver | None = None,
        session_resolver: Callable[[], Path | None] | None = None,
    ) -> PromptResponse:
        """Process a prompt file from disk without attachment.

        ``cancel_event`` targets one browser run without affecting sibling
        jobs. ``event_observer`` optionally receives every emitted lifecycle
        event so a surface can render event-level status (thinking /
        streaming / prompting) for the run.

        ``session_resolver`` optionally returns the session pool path chosen
        by session rotation; the pipeline builds its own AppConfig, so
        without the resolver a pool selection made upstream by the surface
        is silently dropped and the default session is used.
        """
        ...

    @abstractmethod
    def request_cancel(self, cancel_event: CancelToken) -> bool:
        """Register ``cancel_event`` so setting it stops the matching in-flight run.

        Cancellation is part of the seam so surfaces and the Swarm
        orchestrator can stop per-slot work without reaching for
        implementation-only methods. Registering an event must not start,
        join, or block on any run.

        Returns True only when an in-flight run was stopped, so a cancel
        aimed at a run that already finished reports zero (FR-PROMPT-004).
        """
        ...


class IAttachmentPromptProtocol(ABC):
    """Attachment-prompt capability: upload a document, then run the prompt file."""

    @abstractmethod
    def execute(self, request: PromptRequest) -> PromptResponse:
        """Run the prompt verb this capability serves; return its response."""
        ...

    @abstractmethod
    def process_prompt_with_attachment(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        cancel_event: CancelToken | None = None,
        event_observer: LifecycleObserver | None = None,
        session_resolver: Callable[[], Path | None] | None = None,
    ) -> PromptResponse:
        """Process a prompt file from disk with document attachment.

        ``cancel_event`` targets one browser run without affecting sibling
        jobs. ``event_observer`` optionally receives every emitted lifecycle
        event so a surface can render event-level status (thinking /
        streaming / prompting) for the run.
        """
        ...

    @abstractmethod
    def request_cancel(self, cancel_event: CancelToken) -> bool:
        """Register ``cancel_event`` so setting it stops the matching in-flight run.

        Cancellation is part of the seam so surfaces and the Swarm
        orchestrator can stop per-slot work without reaching for
        implementation-only methods. Registering an event must not start,
        join, or block on any run.

        Returns True only when an in-flight run was stopped, so a cancel
        aimed at a run that already finished reports zero (FR-PROMPT-004).
        """
        ...


class IPromptFlowProtocol(ABC):
    """Shared prompt dispatch/response-wait flow capability.

    Two methods: the inject → send → wait flow with retry and rollback, and
    the mid-stream cut handler that persists the partial artifact with the
    honest verdict. Implemented by ``PromptFlowDispatcher`` and consumed by
    the direct, file, and attachment prompt adapters via dependency
    injection.
    """

    @abstractmethod
    def dispatch_and_wait_for_response(
        self,
        page: Page,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        emitter: LifecycleEmitter,
        state: LifecycleState,
        observability: IObservabilityProtocol,
        filepath: Path,
        prompt: str,
        msg_count_before: MessageCount,
        timeout_sec: int,
        active_cfg: AppConfig,
        sender_config: SenderConfig | None = None,
        document_parsed: bool = True,
        cancel_event: CancelToken | None = None,
    ) -> StreamVerdict:
        """Inject the prompt, send it, and wait for the AI response.

        Retries on rate-limit and response-timeout errors; raises
        ``RunCancelledError`` when ``cancel_event`` is set, and
        ``StuckDetectedError`` is terminal without a retry. The returned
        :class:`StreamVerdict` carries the text plus the extraction verdict.
        """
        ...

    @abstractmethod
    def mid_stream_cut_outcome(
        self,
        exc: BaseException,
        page: Page,
        *,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
        out_path: Path,
        prompt_path: Path,
        elapsed: float,
        ctx: RunContext,
        emitter: LifecycleEmitter | None,
    ) -> PromptResponse:
        """Persist the partial artifact after a mid-stream cut (BE-1-003).

        Shared by the file, attachment, and direct pipelines: a stall or a
        hard cut still saves whatever the monitor last saw, so the artifact
        is inspectable, and reports ``stalled`` for the stall detector or
        ``incomplete`` for any other non-terminal end (the timeout family).
        Adapters reach it through this seam so the policy lives in one
        implementation without a capabilities-layer self-import.
        """
        ...


class IRunCancelProtocol(ABC):
    """Contract for the shared targeted-cancel registry of in-flight runs.

    Implemented by ``capabilities_run_cancel_registry.CapabilitiesRunCancelRegistry``
    and injected into the prompt file / attachment / swarm orchestrators so
    that a cancel can stop one run's browser context without touching sibling
    runs.  Runs are addressed by their stable ``RunId`` — never by object
    identity of a ``threading.Event`` — so the handle cannot be invalidated
    by a collected or recycled event object.
    """

    @abstractmethod
    def register(self, run_state: RunState) -> None:
        """Track a newly started in-flight run."""
        ...

    @abstractmethod
    def release(self, run_state: RunState) -> None:
        """Drop the entry for a finished run."""
        ...

    @abstractmethod
    def cancel_run(self, run_id: RunId) -> bool:
        """Stop the run identified by ``run_id`` and close its browser context.

        Returns True only when an in-flight run was found and stopped, so a
        cancel on a run that already reached a terminal state is reported
        as False (FR-PROMPT-004).
        """
        ...

    @abstractmethod
    def cancel_by_event(self, cancel_event: CancelToken) -> bool:
        """Cancel the run that was registered with this cancel event.

        Convenience for surface callers that only hold the original
        ``threading.Event``.  Delegates to the stable ``run_id`` lookup
        internally; returns False when the run has already finished (no
        pipeline stopped).
        """
        ...

    @abstractmethod
    def set_active_bctx(self, run_id: RunId, bctx: Any) -> None:
        """Update the live browser context for a registered run (None clears it)."""
        ...

    @abstractmethod
    def active_bctx(self, run_id: RunId) -> Any:
        """Return the live browser context for ``run_id``, or None."""
        ...


# ─── Core capability contracts (merged from common/contract_core_protocol.py) ───
LifecycleObserver = Callable[[QwenEventType, LifecycleEvent], None]


class IUploadProtocol(ABC):
    """File upload capability contract (external Qwen Web UI adaptation)."""

    @abstractmethod
    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        emitter: LifecycleEmitter | None = None,
        web_loaded: HeadlessFlag = HeadlessFlag(True),
    ) -> bool:
        """Attach a file as an attachment. Returns True on success."""

    @abstractmethod
    def validate_file(self, filepath: Path, max_size_bytes: MaxFileSizeBytes | None = None) -> FileSizeBytes:
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
    ) -> StreamVerdict:
        """Wait for a stable assistant response; return its text and verdict.

        Raises ``ResponseDetectionTimeoutError`` / ``StuckDetectedError`` /
        ``RunCancelledError`` instead of ever answering ``None``, so every
        caller can consume one concrete verdict type.

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
    "IAttachmentPromptProtocol",
    "IDirectPromptProtocol",
    "IFolderCompileProtocol",
    "IFolderToAttachmentProtocol",
    "IInjectionProtocol",
    "IPromptFileProtocol",
    "IPromptFlowProtocol",
    "IRunCancelProtocol",
    "ISaverProtocol",
    "ISendProtocol",
    "IStreamProtocol",
    "IUploadProtocol",
]

# Layer-symbol registry (runtime reference for harness/loader introspection).
_layer_symbols = {
    "LifecycleObserver": LifecycleObserver,
    "IUploadProtocol": IUploadProtocol,
    "IFolderCompileProtocol": IFolderCompileProtocol,
    "IFolderToAttachmentProtocol": IFolderToAttachmentProtocol,
    "IInjectionProtocol": IInjectionProtocol,
    "ISendProtocol": ISendProtocol,
    "IStreamProtocol": IStreamProtocol,
    "ISaverProtocol": ISaverProtocol,
    "IAttachmentPromptProtocol": IAttachmentPromptProtocol,
    "IDirectPromptProtocol": IDirectPromptProtocol,
    "IPromptFileProtocol": IPromptFileProtocol,
    "IPromptFlowProtocol": IPromptFlowProtocol,
    "IRunCancelProtocol": IRunCancelProtocol,
}
