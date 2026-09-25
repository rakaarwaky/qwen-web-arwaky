# BACKLOG — CLI and Textual TUI

Feature prefix: `CLI-`. Last Updated: **2026-09-24**.

State and Health vocabulary, verification requirements, ownership rules, and ID policy are defined only in the root [ROADMAP](../../ROADMAP.md#state-definitions) and [Status Policy](../../ROADMAP.md#status-policy).

## Current Condition

- Done: `git show d8a9b60:modules/cli/FRD.md` returns the shipped CLI/TUI specification at commit `d8a9b60`.
- In Progress: None.
- Blocked: None.
- Next: `CLI-01`, `CLI-02`, `CLI-03`, `CLI-04`.

## Backlog

| ID | Item | Priority | State | Health | Owner | Actual Condition | Next | Updated |
|---|---|---|---|---|---|---|---|---|
| CLI-01 | Unify output-destination behavior and filesystem-edge acceptance | P1 | Ready | At Risk | — | Open findings [#373](https://github.com/rakaarwaky/qwen-web-arwaky/issues/373) and [#280](https://github.com/rakaarwaky/qwen-web-arwaky/issues/280) report divergent destination rules and missing acceptance cases. No current-commit reproduction is attached to this row. | Build a path-resolution matrix for direct, file, attachment, and TUI runs; reproduce on `d8a9b60`; specify one rule before changing code. | 2026-09-24 |
| CLI-02 | Complete update/rollback contract, tests, and cross-platform behavior | P1 | Refinement | At Risk | — | Findings [#379](https://github.com/rakaarwaky/qwen-web-arwaky/issues/379), [#367](https://github.com/rakaarwaky/qwen-web-arwaky/issues/367), [#334](https://github.com/rakaarwaky/qwen-web-arwaky/issues/334), [#294](https://github.com/rakaarwaky/qwen-web-arwaky/issues/294), [#293](https://github.com/rakaarwaky/qwen-web-arwaky/issues/293), and [#279](https://github.com/rakaarwaky/qwen-web-arwaky/issues/279) span protocol drift, POSIX assumptions, subprocess coverage, smoke checks, and rollback acceptance. The FRD now lists `update`, so stale portions require revalidation. | Revalidate each claim, define rollback acceptance, and split only confirmed implementation work. | 2026-09-24 |
| CLI-03 | Remove redundant login validation and add a functional doctor smoke gate | P1 | Refinement | On Track | — | Findings [#381](https://github.com/rakaarwaky/qwen-web-arwaky/issues/381) and [#322](https://github.com/rakaarwaky/qwen-web-arwaky/issues/322) remain open; neither has verification evidence against the current baseline in this backlog. | Trace the login lifecycle and define a non-destructive doctor smoke scenario with unit-testable boundaries. | 2026-09-24 |
| CLI-04 | Lock TUI filesystem and async interaction behavior in documented tests | P2 | Ready | On Track | — | Finding [#335](https://github.com/rakaarwaky/qwen-web-arwaky/issues/335) reports missing Textual async-runner guidance; existing TUI unit tests are present but their required workflow is not documented in `TEST.md`. | Document the test runner and add acceptance coverage identified by `CLI-01`. | 2026-09-24 |

## Dependencies and Exit Evidence

- `CLI-01` depends on the Core output/path contracts remaining explicit.
- `CLI-02` depends on the shared update protocol and release infrastructure.
- Authenticated browser acceptance contributes to workspace gate `WS-03`; it is not duplicated as a CLI row.
- A row can become Done only with the exact verification command, its result, and the implementing commit recorded in `Actual Condition`.
