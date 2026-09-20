"""Agent: attachment prompt orchestrator (AES405).

Orchestrates prompt execution with mandatory document file attachment (.pdf, .md, .txt).
Supports folder-to-attachment compilation (folder -> single markdown file).
"""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import build_app_config
from modules.core.src.utility_core_dom_helper import setup_lifecycle_state
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.core.src.utility_core_io_writer import save_orchestrator_output
from modules.shared.src.contract_core_aggregate import IAttachmentPromptAggregate, IPromptFlowAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IFolderToAttachmentProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
    IUploadProtocol,
)
from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_error import RunCancelledError, UploadFailureError
from modules.shared.src.taxonomy_core_event import PIPELINE_EVENT_SEQUENCE
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    AttachmentPath,
    HeadlessFlag,
    JobName,
    OutputPath,
    PromptPath,
    ResponseText,
    RunContext,
    RunId,
    SenderConfig,
)


@dataclass
class _RunState:
    """Per-run cancellation and browser context state.

    One instance per ``process_prompt_with_attachment`` invocation so that
    concurrent TUI slots sharing one orchestrator instance never touch each
    other's cancel flag or browser context.

    ``cancel_event`` is owned by the caller when provided (targeted cancel),
    otherwise a private event is created for internal fail-fast checks.
    """

    cancel_event: threading.Event = field(default_factory=threading.Event)
    active_bctx: object | None = None
    bctx_lock: threading.Lock = field(default_factory=threading.Lock)


def _make_run_state(cancel_event: threading.Event | None) -> _RunState:
    """Create a per-run state, reusing the caller's event when supplied."""
    if cancel_event is not None:
        return _RunState(cancel_event=cancel_event)
    return _RunState()


class AttachmentPromptOrchestrator(IAttachmentPromptAggregate):
    """Orchestrates prompt execution with document file attachment."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        uploader: IUploadProtocol,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
        flow: IPromptFlowAggregate,
        folder_adapter: IFolderToAttachmentProtocol,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._uploader = uploader
        self._saver = saver
        self._observability = observability
        self._flow = flow
        self._folder_adapter = folder_adapter
        # Registry: cancel_event -> _RunState for every active run.
        # Keyed on the caller's threading.Event so the TUI worker can target
        # one specific run without touching sibling runs.
        self._run_registry: dict[int, _RunState] = {}
        self._registry_lock = threading.Lock()

    def request_cancel(self, cancel_event: threading.Event) -> None:
        """Cancel a specific in-flight run identified by its cancel event.

        The caller (e.g. the TUI slot worker) creates its own
        ``threading.Event`` per run, passes it into
        ``process_prompt_with_attachment``, and later calls this method with
        the same event to stop *only that run*. Sibling runs holding
        different events are unaffected.
        """
        with self._registry_lock:
            run_state = self._run_registry.get(id(cancel_event))
        if run_state is None:
            cancel_event.set()
            return
        cancel_event.set()
        with run_state.bctx_lock:
            bctx = run_state.active_bctx
        if bctx is not None:
            close_fn = getattr(bctx, "close", None)
            if callable(close_fn):
                with contextlib.suppress(Exception):
                    close_fn()

    def process_prompt_with_attachment(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
        cancel_event: threading.Event | None = None,
    ) -> ResponseText:
        """Pipeline 3: Process a prompt file from disk with document attachment.

        Supports folder paths: if attachment_file is a folder, it will be
        compiled to a single markdown file before upload.

        Pass ``cancel_event`` to enable targeted cancellation: the TUI
        worker creates one ``threading.Event`` per slot and hands it in;
        ``request_cancel`` can then stop only that slot's run without
        closing sibling slots' browser contexts. When omitted (non-TUI
        callers), a private event is used internally and the run is not
        externally cancellable.
        """
        ctx = RunContext()
        run_state = _make_run_state(cancel_event)
        with self._registry_lock:
            self._run_registry[id(run_state.cancel_event)] = run_state
        try:
            p_path = Path(prompt_file).resolve()
            if not p_path.exists():
                raise FileNotFoundError(f"Input file not found: {p_path}")

            self._observability.bind_run_context(RunId(ctx.run_id), job_name=JobName(p_path.stem))
            self._observability.attach_run_log(job_name=JobName(p_path.stem), run_id=RunId(ctx.run_id))

            att_path = self._folder_adapter.resolve_to_attachment(Path(attachment_file))

            out_path = Path(output_file).resolve() if output_file else DEFAULT_OUTPUT / p_path.name
            if out_path.is_dir():
                out_path = out_path / f"{p_path.stem}_output.md"

            cfg = build_app_config(
                input_path=p_path,
                file_path=att_path,
                output_path=out_path,
                headless=headless,
            )
            emitter, state = setup_lifecycle_state(self._observability.get_logger(), PIPELINE_EVENT_SEQUENCE)

            t0 = time.time()
            with self._browser.browser_session(cfg) as bctx:
                with run_state.bctx_lock:
                    run_state.active_bctx = bctx
                try:
                    if run_state.cancel_event.is_set():
                        raise RunCancelledError("Cancelled by user before browser launch")
                    page = bctx.pages[0] if bctx.pages else bctx.new_page()
                    text = self._execute_attachment_on_page(
                        page, p_path, att_path, cfg.request_timeout, cfg, emitter, state, run_state.cancel_event
                    )
                finally:
                    with run_state.bctx_lock:
                        run_state.active_bctx = None
            dur = time.time() - t0
            save_orchestrator_output(self._saver, out_path, p_path, text, dur, ctx, emitter=emitter)
            return ResponseText(f"Successfully processed {p_path.name} with attachment {att_path.name} -> {out_path}")
        except Exception as exc:
            return to_error_response(exc)
        finally:
            with self._registry_lock:
                self._run_registry.pop(id(run_state.cancel_event), None)
            self._observability.detach_run_log(RunId(ctx.run_id))
            self._observability.clear_run_context()

    def _execute_attachment_on_page(
        self,
        page: Page,
        filepath: Path,
        att_path: Path,
        timeout_sec: int,
        active_cfg: AppConfig,
        emitter: LifecycleEmitter,
        state: LifecycleState,
        cancel_event: threading.Event | None = None,
    ) -> str:
        logger = self._observability.get_logger()

        prompt = filepath.read_text(encoding="utf-8").strip()

        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
        msg_count_before = self._sender.count_messages(page)

        self._injector.find_input(page)
        attached = self._uploader.upload_attachment(
            page, att_path, emitter=emitter, web_loaded=HeadlessFlag(state.web_loaded)
        )
        if not attached or not state.file_uploaded or not state.document_parsed:
            upload_error = getattr(self._uploader, "last_error", None)
            detail = f": {upload_error}" if upload_error else ""
            logger.error("File upload or parsing could not be positively verified: %s%s", att_path.name, detail)
            raise UploadFailureError(f"Attachment upload/parsing failed for {att_path.name}{detail}")

        # Use a generous timeout so _wait_for_send_enabled can hold for
        # long document parsing (up to 120s) before the first click attempt.
        send_cfg = SenderConfig(
            click_timeout_ms=120_000,
            try_enter_key_fallback=True,
        )
        return self._flow.dispatch_and_wait_for_response(
            page=page,
            injector=self._injector,
            sender=self._sender,
            streamer=self._streamer,
            emitter=emitter,
            state=state,
            observability=self._observability,
            filepath=filepath,
            prompt=prompt,
            msg_count_before=msg_count_before,
            timeout_sec=timeout_sec,
            active_cfg=active_cfg,
            sender_config=send_cfg,
            document_parsed=state.document_parsed,
            cancel_event=cancel_event,
        )


__all__ = ["AttachmentPromptOrchestrator"]
