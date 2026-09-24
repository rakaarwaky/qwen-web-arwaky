# Product Roadmap: qwen-web

PRD: [PRD.md](PRD.md)
Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
Last Updated: 2026-09-24

## Documentation Boundary

A feature folder is a workspace member that contains an `agent_*_orchestrator`
file. Every feature folder must contain both `FRD.md` and `BACKLOG.md`. A
workspace member without an orchestrator is not a feature folder and must
contain neither document. Kernel and shared layers are never feature folders.
The root product documents are this roadmap and `PRD.md`.

Under the current tree, `modules/core` is the only feature folder. The
`modules/cli`, `modules/mcp`, `modules/shared`, and `modules/templates` members
are surfaces or supporting layers; their product-level requirements are owned
by `PRD.md`, and their implementation relationships are described by the Core
FRD and root architecture.

## State Vocabulary

These are the only values allowed in a feature backlog's **State** column.

| State | Meaning | Entry condition | Exit condition |
|---|---|---|---|
| New | Recorded but not yet refined. | A scoped need has an ID and FRD reference. | Acceptance and dependencies are clear. |
| Ready | Refined and available to start. | Acceptance, owner, and dependencies are known. | Work starts or a blocker is discovered. |
| In Progress | Implementation or verification is active. | An owner has started the work. | Evidence supports Done, or a blocker stops progress. |
| Blocked | Work cannot proceed. | The clearing condition and external owner are recorded. | The clearing condition is met. |
| Done | Implemented and verified on the development line. | A reproducible command and commit hash prove the row's actual condition. | The row is selected and verified for a release. |
| Released | Delivered in a published version. | Done evidence plus the release tag or artifact is recorded. | Terminal state. |

## Health Vocabulary

These are the only values allowed when summarizing roadmap or release health.
They do not replace backlog row states.

| Health | Meaning |
|---|---|
| On Track | No known blocker threatens the stated next action. |
| At Risk | A known issue may prevent the stated next action. |
| Blocked | A named clearing condition prevents the stated next action. |
| Complete | All scoped rows have evidence and no release blocker remains. |

## Evidence Policy

- `Done` requires a passing command, its result, a commit hash, and the date of
  verification in the feature backlog.
- `Released` requires the same evidence plus a release tag or immutable
  artifact reference.
- A checked box, an author's assertion, or a source path alone is not evidence.
- If evidence cannot be reproduced, move the row to `In Progress` or `Blocked`.
- Scenario evidence must map every FRD scenario to an automated test, proxy,
  manual procedure, or explicit gap.

## Verification

Run `python scripts/check_docs.py .` for the repository-native documentation
contract check. `scripts/gates.sh` runs the same check before source-quality
gates. Environments that provide the Agentic Alliance CLI may additionally run
`aa check docs .`.

## Current Product Condition

| Area | Health | Evidence / next action |
|---|---|---|
| Core automation feature | On Track | See [modules/core/BACKLOG.md](modules/core/BACKLOG.md). |
| CLI surface | On Track | Product scope remains in [PRD.md](PRD.md); verification is included in the Core backlog where it exercises Core requirements. |
| MCP surface | On Track | Product scope remains in [PRD.md](PRD.md); MCP is not a feature folder because it has no orchestrator. |
| Shared kernel | Complete | Architecture-only member; feature documents are intentionally absent. |

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-09-24 | Established feature-document boundaries, shared state vocabulary, health vocabulary, and evidence policy. | @arena-agent |
