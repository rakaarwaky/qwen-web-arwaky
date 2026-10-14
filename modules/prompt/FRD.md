# PROMPT Functional Requirements Document

## Reference

- PRD: [PRD.md](../../PRD.md)
- Backlog: [BACKLOG.md](BACKLOG.md)

## System Overview

The prompt feature drives one prompt through the authenticated chat: it
injects the prompt, attaches any attachment, sends it, follows the stream
until a terminal state, and saves the response. One orchestrator routes
each prompt verb to the adapter that serves it, and the shared-flow
orchestrator drives the inject, dispatch, monitor, and save steps so the
surfaces and job runners see one pipeline.

## Functional Requirements

### FR-PROMPT-001: Run a direct prompt

- **Description**: Send a text prompt to the live chat and save the response.
- **Input**: A prompt request carrying the text, the run configuration, and the optional output path.
- **Output**: A prompt response carrying the saved path and the extraction verdict.
- **Business Rules**:
  - An empty prompt is rejected at the surface, so an adapter never receives an empty text.
  - The response is saved to the operator's named output destination.
- **Edge Cases**: A response the stream never stops emitting is cut off at the configured stall detector and reported as incomplete.
- **Error Handling**: A send that fails surfaces a prompt failure carrying the reason, and the run records a failure outcome in metrics.

### FR-PROMPT-002: Run a file prompt

- **Description**: Send the contents of a prompt file through the pipeline.
- **Input**: A prompt request naming the file path, the run configuration, and the optional output path.
- **Output**: A prompt response carrying the saved path and the extraction verdict.
- **Business Rules**: The file must exist and be readable before the pipeline starts.
- **Edge Cases**: A file that cannot be read surfaces a file error naming the path.
- **Error Handling**: A pipeline failure mid-stream surfaces the failure reason and keeps the response file, so an interrupted extraction is inspectable.

### FR-PROMPT-003: Run an attachment prompt

- **Description**: Send a prompt with one attached file.
- **Input**: A prompt request naming the prompt text, the attachment path, the run configuration, and the optional output path.
- **Output**: A prompt response carrying the saved path and the extraction verdict.
- **Business Rules**:
  - The attachment must pass the size and type limits the upload seam enforces before the send.
  - An attachment that uploads but fails mid-stream still reports the response file when the extraction recovers.
- **Edge Cases**: An attachment that exceeds the upload ceiling is rejected at upload with the limit named.
- **Error Handling**: An attachment failure surfaces an upload error naming the file; the pipeline does not retry the send.

### FR-PROMPT-004: Cancel a running prompt

- **Description**: Stop the file and attachment pipelines a run owns.
- **Input**: A cancel request naming the run-scoped cancel event.
- **Output**: The number of pipelines that stopped.
- **Business Rules**:
  - A direct prompt has no cancel registry, so cancel reports zero pipelines stopped for it.
  - A pipeline that already reached a terminal state is not reported as stopped.
- **Edge Cases**: A cancel on a run with no active pipeline reports zero.
- **Error Handling**: A cancel whose event is not registered surfaces no error; the pipeline was already terminal.

### FR-PROMPT-005: Targeted run cancellation

- **Description**: Maintain a thread-safe registry of in-flight runs so a cancel stops exactly one run's browser context without touching sibling runs on the same instance.
- **Input**: A run-scoped ``RunState`` carrying the stable ``run_id`` and an optional ``cancel_event``.
- **Output**: The registered verdict, the released verdict, or the cancelled verdict.
- **Business Rules**:
  - Entries are keyed by the stable ``run_id``, never by the object identity of a ``threading.Event``, so a cancel targets one specific run even when events are recreated across threads.
  - A private event index supports the ``request_cancel`` convenience path used by surfaces that hold only the original ``threading.Event``.
  - Cancelling a run sets its ``cancel_event`` so any in-progress flow check observes the new state, and closes its live browser context so the underlying browser process stops.
- **Edge Cases**: A cancel for a run that already finished is a no-op; a run whose browser context is already gone still sets the event.
- **Error Handling**: No error is raised; a missing run is a silent no-op.

### FR-PROMPT-006: Monitor the response stream

- **Description**: Follow the response stream until a terminal state is reached or the stall detector fires.
- **Input**: The live page, the stream's selectors, and the configured ceilings.
- **Output**: The extraction verdict: complete, stalled, or incomplete.
- **Business Rules**:
  - The wall-clock response ceiling is a ceiling, not an idle budget; a long thinking phase emits no forward event, so a short ceiling aborts healthy runs.
  - A stalled stream is distinguished from a complete one so a caller can decide whether to retry.
- **Edge Cases**: A stream that emits no forward event for the full ceiling reports stalled, not complete.
- **Error Handling**: A monitor that cannot read the stream reports the extraction incomplete rather than raising into the caller.

### FR-PROMPT-007: Inject prompt text into the chat

- **Description**: Locate the chat input and inject the prompt text via multi-strategy DOM injection.
- **Input**: A page, the prompt text, and the optional injector configuration.
- **Output**: The input element that received the text, or a not-found error.
- **Business Rules**: The input element must exist before injection; a missing input is a hard error.
- **Edge Cases**: A chat that has not loaded reports a not-found error for the input element.
- **Error Handling**: A not-found input surfaces an element-not-found error naming the selector.

### FR-PROMPT-008: Trigger the send action

- **Description**: Click the send control and count the chat turns that result.
- **Input**: A page, a lifecycle emitter, and the optional send configuration.
- **Output**: The number of chat turns after the send, and the latest assistant text.
- **Business Rules**: The send control must be clickable; a disabled control is a hard error.
- **Edge Cases**: A send that produces no new turn is reported as a dispatch failure.
- **Error Handling**: A send that fails surfaces a send-dispatch error carrying the reason.

### FR-PROMPT-009: Save the response to the operator's destination

- **Description**: Persist the processed response with a metadata header and sidecar.
- **Input**: The output path, the response text, the run context, the source file, duration, and character counts.
- **Output**: A written response file at the named destination.
- **Business Rules**: The output path must be writable; a non-writable path is a hard error.
- **Edge Cases**: A mid-stream extraction failure keeps the response file so an operator can inspect it.
- **Error Handling**: A write failure surfaces an output-write error naming the path.

### FR-PROMPT-010: Upload an attachment

- **Description**: Attach a file to the chat as an attachment, with pre-flight validation.
- **Input**: A page, the file path, the optional upload configuration, and the optional lifecycle emitter.
- **Output**: A boolean indicating whether the attachment was accepted.
- **Business Rules**: A file exceeding the upload limit is rejected with the limit named.
- **Edge Cases**: A file that cannot be read surfaces a file error naming the path.
- **Error Handling**: An upload failure surfaces an upload-failure error carrying the reason.

### FR-PROMPT-011: Compile a folder to a single markdown file

- **Description**: Compile folder contents to a single markdown file, optionally following imports.
- **Input**: A folder path, an optional output path, a maximum recursion depth, and an import depth.
- **Output**: The compiled markdown file path.
- **Business Rules**: The folder must exist and be readable before compilation starts.
- **Edge Cases**: A folder that cannot be read surfaces a file error naming the path.
- **Error Handling**: A compile failure surfaces the reason and leaves the partial output for inspection.

### FR-PROMPT-012: Resolve a folder to an attachment-ready file

- **Description**: Resolve a path to an attachment-ready file, compiling folders to markdown when needed.
- **Input**: A path, a maximum recursion depth, and an import depth.
- **Output**: A path to an attachment-ready file.
- **Business Rules**: A directory is compiled to markdown before it is used as an attachment.
- **Edge Cases**: A path that is neither a file nor a folder is rejected.
- **Error Handling**: A resolution failure surfaces the reason and names the path.

## API Contract

### Protocol API

Each row below is one method on one protocol class (FR = 1 protocol class).
The class is named in the Description column.

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `process_direct_prompt` | text, timeout, headless, output path | prompt response | prompt failure | generation finished | Run a direct prompt. (IDirectPromptProtocol) |
| `process_prompt_file_only` | file path, timeout, headless, output path | prompt response | file error, prompt failure | generation finished | Run a file prompt. (IPromptFileProtocol) |
| `process_prompt_with_attachment` | text, attachment path, timeout, headless, output path | prompt response | upload error, prompt failure | generation finished | Run an attachment prompt. (IAttachmentPromptProtocol) |
| `request_cancel` | run cancel event | stopped-pipelines count | none | none | Stop the file and attachment pipelines a run owns. (IPromptFlowProtocol) |
| `dispatch_and_wait_for_response` | dispatch input, stream configuration | extraction verdict | stream error | generation finished | Drive one send and follow its stream. (IPromptFlowProtocol) |
| `register` | run-scoped cancel state | registered verdict | none | none | Register a run's cancel state. (IRunCancelProtocol) |
| `release` | run-scoped cancel state | released verdict | none | none | Release a run's cancel state. (IRunCancelProtocol) |
| `cancel_run` | run-scoped cancel state | cancelled verdict | none | none | Cancel one run and close its browser context. (IRunCancelProtocol) |
| `cancel_by_event` | original ``threading.Event`` | cancelled verdict | none | none | Cancel the run registered with the original event. (IRunCancelProtocol) |
| `upload_attachment` | page, filepath, config, emitter, web_loaded | accepted flag | upload error | file uploaded | Attach a file as an attachment. (IUploadProtocol) |
| `validate_file` | filepath, max_size_mb | file size in bytes | file error | none | Pre-flight validation of an attachment. (IUploadProtocol) |
| `compile_folder` | folder path, output path, max_depth, import_depth | compiled markdown path | file error | document parsed | Compile folder contents to a single markdown file. (IFolderCompileProtocol) |
| `resolve_to_attachment` | path, max_depth, import_depth | attachment-ready path | file error | none | Resolve a path to an attachment-ready file. (IFolderToAttachmentProtocol) |
| `is_folder` | path | directory flag | none | none | Check whether a path is a directory. (IFolderToAttachmentProtocol) |
| `find_input` | page, config | input element | element not found | none | Locate the chat input element. (IInjectionProtocol) |
| `inject_text` | page, text, config | none | element not found | prompt injected | Inject prompt text via multi-strategy DOM injection. (IInjectionProtocol) |
| `click_send` | page, emitter, config, document_parsed | none | send dispatch error | send clicked | Trigger the send action. (ISendProtocol) |
| `count_messages` | page | chat turn count | none | none | Count chat turns. (ISendProtocol) |
| `latest_message_text` | page | response text | none | none | Return the latest assistant response text. (ISendProtocol) |
| `wait_for_response` | page, timeout, msg_count_before, emitter, config, cancel_event | response text | stream error, run cancelled | generation finished | Wait for a stable assistant response. (IStreamProtocol) |
| `is_generation_complete` | page | generation flag | none | none | True when Qwen has finished generating. (IStreamProtocol) |
| `is_thinking_active` | page | thinking flag | none | none | True when Qwen is currently thinking/streaming. (IStreamProtocol) |
| `write_output` | path, content, ctx, src, dur, input_chars, output_chars, config | none | output write error | output copied | Write processed output with metadata header + sidecar. (ISaverProtocol) |

### Aggregate API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `execute` | prompt request naming the verb | prompt response carrying the saved path or the failure reason | verb error | generation finished, failed | Single entry point every surface and job runner calls to run any prompt verb. |

## Integration Points

| System | Direction | Purpose | Failure mode |
|---|---|---|---|
| Surfaces | in | Run one prompt verb | prompt failure -> surface reports the reason |
| Jobs orchestrators | in | Run a queued prompt outside the caller window | prompt failure -> job record carries the error |
| Swarm orchestrators | in | Fan one prompt out across browsers | prompt failure -> that leg fails |
| Browser aggregate | out | Obtain the authenticated page per run | authentication error -> the run fails before the send |

## Non-functional Requirements

| Metric | Target | Measurement method |
|---|---|---|
| Stream stall detection | every stalled stream reports incomplete, not complete | injection of a stream that emits no forward event |
| Response save | every completed run writes the response file | file presence after a completed run |
| Cancel latency | a running pipeline stops on the first poll after the cancel event | timing the cancel verb against pipeline state |

## Test Scenarios

- A direct prompt produces a response file at the operator's named destination.
- A stalled stream reports incomplete and does not retry the send.
- A cancel on a file pipeline reports one stopped pipeline.
- An attachment exceeding the upload limit is rejected with the limit named.
- A response file survives a mid-stream extraction failure so an operator can inspect it.
- A cancel for a run with no active pipeline is a no-op and does not affect sibling runs.

## Assumptions & Constraints

- The DOM selectors the stream monitor matches are pinned by regression tests; changing them is a deliberate, reviewed change.
- The wall-clock response ceiling is configured per environment; the stall detector is the one that catches a genuinely wedged stream.

## Glossary

- **Stream monitor**: The seam that follows the response until a terminal state.
- **Stall detector**: The check that distinguishes a slow response from a wedged one.
- **Extraction verdict**: The result of the monitor: complete, stalled, or incomplete.
