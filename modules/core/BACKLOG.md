# BACKLOG — Core Automation Engine

Feature prefix: `CORE-`. Last Updated: **2026-09-24**.

State and Health vocabulary, verification requirements, ownership rules, and ID policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions) and [Status Policy](../../ROADMAP.md#status-policy).

## Current Condition

- Done: `git show d8a9b60:modules/core/FRD.md` returns the 13-capability and swarm specification at commit `d8a9b60`.
- In Progress: None.
- Blocked: None.
- Next: `CORE-01`, `CORE-02`, `CORE-03`, `CORE-04`, `CORE-05`, `CORE-06`, `CORE-07`.

## Backlog

| ID | Item | Priority | State | Health | Owner | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|---|
| CORE-01 | Verify patient attachment send and challenge-safe swarm behavior | P0 | QA | At Risk | — | PRs #423/#424 added parsing holds and retry-gate preservation, and regression tests exist in the `d8a9b60` baseline. The headed single-attachment and 10-role scenarios in [`ISSUE.md`](../../ISSUE.md) are still unchecked, so production behavior is not verified. | Run the `WS-03` manual matrix; capture commit, commands, timing, ACK behavior, retries, and any bot-verification page. | 2026-09-24 |
| CORE-02 | Bound async job and swarm lifecycle, cancellation, queueing, and host resources | P0 | Refinement | At Risk | — | Open findings [#377](https://github.com/rakaarwaky/qwen-web-arwaky/issues/377), [#376](https://github.com/rakaarwaky/qwen-web-arwaky/issues/376), [#375](https://github.com/rakaarwaky/qwen-web-arwaky/issues/375), [#363](https://github.com/rakaarwaky/qwen-web-arwaky/issues/363), [#362](https://github.com/rakaarwaky/qwen-web-arwaky/issues/362), [#361](https://github.com/rakaarwaky/qwen-web-arwaky/issues/361), [#291](https://github.com/rakaarwaky/qwen-web-arwaky/issues/291), and [#277](https://github.com/rakaarwaky/qwen-web-arwaky/issues/277) report leaked executors, zombie jobs, queue/backpressure gaps, cancellation drift, and missing resource governance. | Reproduce cancellation and crash recovery first; write one bounded lifecycle contract and then split implementation rows if needed. | 2026-09-24 |
| CORE-03 | Harden stream completion and model-selection resilience | P0 | Refinement | At Risk | — | Findings [#382](https://github.com/rakaarwaky/qwen-web-arwaky/issues/382), [#374](https://github.com/rakaarwaky/qwen-web-arwaky/issues/374), and [#283](https://github.com/rakaarwaky/qwen-web-arwaky/issues/283) question reload/stability interaction and hardcoded model verification. The FRD describes a safety breaker but no evidence here resolves those reports. | Add deterministic reload/stability tests and specify configurable-model fallback behavior before implementation. | 2026-09-24 |
| CORE-04 | Restore one-capability/one-protocol naming and layer boundaries | P1 | Refinement | At Risk | — | Findings [#359](https://github.com/rakaarwaky/qwen-web-arwaky/issues/359), [#358](https://github.com/rakaarwaky/qwen-web-arwaky/issues/358), [#357](https://github.com/rakaarwaky/qwen-web-arwaky/issues/357), and [#316](https://github.com/rakaarwaky/qwen-web-arwaky/issues/316) report protocol granularity, surface-oriented capability names, and Root injection concerns. | Compare every claim with the architecture lint and current contracts; write migration order for confirmed violations. | 2026-09-24 |
| CORE-05 | Harden browser, session, folder-upload, and deletion security boundaries | P0 | Refinement | At Risk | — | Findings [#351](https://github.com/rakaarwaky/qwen-web-arwaky/issues/351), [#347](https://github.com/rakaarwaky/qwen-web-arwaky/issues/347), [#346](https://github.com/rakaarwaky/qwen-web-arwaky/issues/346), [#345](https://github.com/rakaarwaky/qwen-web-arwaky/issues/345), [#344](https://github.com/rakaarwaky/qwen-web-arwaky/issues/344), [#337](https://github.com/rakaarwaky/qwen-web-arwaky/issues/337), [#300](https://github.com/rakaarwaky/qwen-web-arwaky/issues/300), and [#290](https://github.com/rakaarwaky/qwen-web-arwaky/issues/290) cover secret uploads, executable trust, profile cloning, path deletion, sandbox defaults, Windows safety, and session recovery. | Threat-model authenticated profile handling and destructive paths; prioritize reproducible credential-loss or arbitrary-deletion cases. | 2026-09-24 |
| CORE-06 | Make observability, security events, permissions, and production gates explicit | P1 | Refinement | At Risk | — | Findings [#366](https://github.com/rakaarwaky/qwen-web-arwaky/issues/366), [#354](https://github.com/rakaarwaky/qwen-web-arwaky/issues/354), [#352](https://github.com/rakaarwaky/qwen-web-arwaky/issues/352), [#297](https://github.com/rakaarwaky/qwen-web-arwaky/issues/297), [#296](https://github.com/rakaarwaky/qwen-web-arwaky/issues/296), and [#292](https://github.com/rakaarwaky/qwen-web-arwaky/issues/292) cover logging consistency, security signals, telemetry egress, path permissions, alerting, and environment contracts. | Inventory emitted data and runtime switches; define secure defaults and a production observability gate. | 2026-09-24 |
| CORE-07 | Reconcile workspace provisioner behavior with its specification | P1 | Ready | On Track | — | Finding [#319](https://github.com/rakaarwaky/qwen-web-arwaky/issues/319) reports more symlinks in implementation than the FRD specifies. Current expected behavior must be chosen before either code or docs change. | Compare provisioner tests, CLI docs, and shipped behavior; amend the incorrect side with acceptance evidence. | 2026-09-24 |

## Dependencies and Exit Evidence

- `CORE-01` supplies the feature evidence required by workspace release gate `WS-03`.
- `CORE-02` defines the execution behavior consumed by MCP row `MCP-01`.
- Cross-cutting policy/runbook and package-manifest work remains in workspace row `WS-04`.
- A row can become Done only with the exact verification command, its result, and the implementing commit recorded in `Actual Condition`; live-browser claims also require the tested mode and session conditions.
