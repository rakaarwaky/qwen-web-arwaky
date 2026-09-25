# BACKLOG — MCP Server Surface

Feature prefix: `MCP-`. Last Updated: **2026-09-24**.

State and Health vocabulary, verification requirements, ownership rules, and ID policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions) and [Status Policy](../../ROADMAP.md#status-policy).

## Current Condition

- Done: `git show d8a9b60:modules/mcp/FRD.md` returns the shipped MCP tool and response specification at commit `d8a9b60`.
- In Progress: None.
- Blocked: None.
- Next: `MCP-01`, `MCP-02`, `MCP-03`.

## Backlog

| ID | Item | Priority | State | Health | Owner | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|---|
| MCP-01 | Guarantee bounded, non-blocking MCP submissions | P0 | Ready | At Risk | — | Finding [#383](https://github.com/rakaarwaky/qwen-web-arwaky/issues/383) reports that rate-limit acquisition can block a tool call for about 60 seconds. Core queue and worker constraints are owned by `CORE-02`; this row owns the MCP request/response boundary. | Reproduce submit latency under saturation and specify immediate `RATE_LIMITED`/backpressure envelopes with timing acceptance. | 2026-09-24 |
| MCP-02 | Mark model output as untrusted at the agent boundary | P0 | Refinement | At Risk | — | Finding [#343](https://github.com/rakaarwaky/qwen-web-arwaky/issues/343) reports that model output is returned to MCP clients without an explicit trust marker, creating an indirect prompt-injection risk. | Define a backward-compatible trust/provenance field and add contract tests for synchronous and async result envelopes. | 2026-09-24 |
| MCP-03 | Reconcile async-tool documentation and complete consumer UAT | P1 | Refinement | On Track | — | Findings [#315](https://github.com/rakaarwaky/qwen-web-arwaky/issues/315) and [#286](https://github.com/rakaarwaky/qwen-web-arwaky/issues/286) report missing Job Manager dependency documentation and MCP consumer sign-off. The FRD now mentions `IJobManagerAggregate`, so #315 may be stale; UAT still lacks detailed error-recovery acceptance. | Revalidate docs against the live `TOOLS` registry, close stale reports, and run consumer UAT for success, rate limit, auth expiry, and failed jobs. | 2026-09-24 |

## Dependencies and Exit Evidence

- `MCP-01` depends on the bounded Core lifecycle in `CORE-02` but independently owns tool-call latency and envelope behavior.
- `MCP-02` must preserve the structured contract described in the FRD.
- Cross-feature documentation drift and release evidence remain in workspace rows `WS-01`, `WS-03`, and `WS-04`.
- A row can become Done only with the exact verification command, its result, and the implementing commit recorded in `Actual Condition`.
