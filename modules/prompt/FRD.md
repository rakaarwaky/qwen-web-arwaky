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

### FR-PROMPT-005: Monitor the response stream

- **Description**: Follow the response stream until a terminal state is reached or the stall detector fires.
- **Input**: The live page, the stream's selectors, and the configured ceilings.
- **Output**: The extraction verdict: complete, stalled, or incomplete.
- **Business Rules**:
  - The wall-clock response ceiling is a ceiling, not an idle budget; a long thinking phase emits no forward event, so a short ceiling aborts healthy runs.
  - A stalled stream is distinguished from a complete one so a caller can decide whether to retry.
- **Edge Cases**: A stream that emits no forward event for the full ceiling reports stalled, not complete.
- **Error Handling**: A monitor that cannot read the stream reports the extraction incomplete rather than raising into the caller.

## API Contract

### Protocol API

| Method | Input | Output | Error | Event | Description |
|---|---|---|---|---|---|
| `process_direct_prompt` | text, timeout, headless, output path | prompt response | prompt failure | generation finished | Run a direct prompt. |
| `process_prompt_file_only` | file path, timeout, headless, output path | prompt response | file error, prompt failure | generation finished | Run a file prompt. |
| `process_prompt_with_attachment` | text, attachment path, timeout, headless, output path | prompt response | upload error, prompt failure | generation finished | Run an attachment prompt. |
| `request_cancel` | run cancel event | stopped-pipelines count | none | none | Stop the file and attachment pipelines a run owns. |
| `execute` | prompt request | prompt response | verb error | dispatch acknowledged | Single entry point over the prompt verb. |
| `dispatch_and_wait_for_response` | dispatch input, stream configuration | extraction verdict | stream error | generation finished | Drive one send and follow its stream. |

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

## Assumptions & Constraints

- The DOM selectors the stream monitor matches are pinned by regression tests; changing them is a deliberate, reviewed change.
- The wall-clock response ceiling is configured per environment; the stall detector is the one that catches a genuinely wedged stream.

## Glossary

- **Stream monitor**: The seam that follows the response until a terminal state.
- **Stall detector**: The check that distinguishes a slow response from a wedged one.
- **Extraction verdict**: The result of the monitor: complete, stalled, or incomplete.
