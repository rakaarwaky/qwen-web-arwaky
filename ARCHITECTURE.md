# Agentic Engineering System Architecture

## Overview

The Agentic Engineering System is a layered, AI-native architecture pattern. It keeps domain models stable, business logic readable, technical detail isolated, and layer boundaries explicit enough for both humans and AI agents to modify the system safely.

## Rule Index

| Code | Group | Name | Severity |
| ------ | --------- | --------------------- | --------------- |
| AES101 | Naming    | Naming Convention     | HIGH            |
| AES102 | Naming    | Suffix/Prefix Rules   | HIGH            |
| AES103 | Naming    | Test File Prefix      | HIGH            |
| AES201 | Import    | Forbidden Import      | CRITICAL        |
| AES202 | Import    | Mandatory Import      | HIGH            |
| AES203 | Import    | Unused Import         | MEDIUM          |
| AES204 | Import    | Dummy Import          | HIGH            |
| AES205 | Import    | Circular Import       | CRITICAL        |
| AES301 | Quality   | File Maximum Limit    | HIGH            |
| AES302 | Quality   | File Minimum Limit    | HIGH            |
| AES303 | Quality   | Mandatory Definition  | HIGH/MEDIUM     |
| AES304 | Quality   | Bypass Comment        | CRITICAL        |
| AES305 | Quality   | Duplication Code      | MEDIUM          |
| AES401 | Role      | Taxonomy Role         | HIGH            |
| AES402 | Role      | Contract Role         | HIGH            |
| AES403 | Role      | Capabilities Role     | HIGH/MEDIUM/LOW |
| AES404 | Role      | Utility Role          | MEDIUM          |
| AES405 | Role      | Agent Role            | HIGH/MEDIUM/LOW |
| AES406 | Role      | Surface Role          | HIGH            |
| AES501 | Orphan    | Taxonomy Orphan       | LOW             |
| AES502 | Orphan    | Contract Orphan       | MEDIUM          |
| AES503 | Orphan    | Capabilities Orphan   | MEDIUM          |
| AES504 | Orphan    | Utility Orphan        | MEDIUM          |
| AES505 | Orphan    | Agent Orphan          | HIGH            |
| AES506 | Orphan    | Surface Orphan        | HIGH/MEDIUM/LOW |
| AES601 | Doc       | AGENTS Document       | HIGH            |
| AES602 | Doc       | README Document       | HIGH            |
| AES603 | Doc       | ARCHITECTURE Document | HIGH            |
| AES604 | Doc       | CONTRIBUTING Document | HIGH            |
| AES605 | Doc       | PRD Document          | HIGH            |
| AES606 | Doc       | ROADMAP Document      | HIGH            |
| AES607 | Doc       | BACKLOG Document      | HIGH            |
| AES608 | Doc       | DATA Document         | HIGH            |
| AES609 | Doc       | FRD Document          | HIGH            |
| AES610 | Doc       | DESIGN Document       | HIGH            |
| AES701 | Structure | Shared Folder Purity  | MEDIUM          |
| AES702 | Structure | Feature Folder Health | MEDIUM          |
| AES703 | Structure | Surface Folder Purity | MEDIUM          |
| AES704 | Structure | Test Suite Coverage   | MEDIUM          |
| AES705 | Structure | Member-Root Placement | MEDIUM          |
| AES706 | Structure | PR-LA Folder Mapping  | MEDIUM          |

---

## Group 1: Naming (AES101–AES103)

Group 1 enforces file naming conventions to ensure clarity and consistency across the codebase.

### Naming Format

| Component | Position | Example               |
| --------- | -------- | --------------------- |
| Layer     | Prefix   | `capabilities`        |
| Concern   | Middle   | `user`                |
| Role      | Suffix   | `checker`             |
| Extension | End      | `.rs` / `.py` / `.ts` |

**Pattern:** `layer_concern_role.rs|py|ts`

### AES101 — Naming Convention

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when | `NAMING_CONVENTION`: file stem is not the `prefix_concept[_concept…]_suffix` shape (all-lowercase, ≥3 underscore-separated words) |
| Scope | Production source files; `tests/`+`benches/` handled by AES103 only |
| Fix | Rename to the layer pattern |

### AES102 — Suffix/Prefix Rules

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when | A file's layer suffix matches neither its layer's allowed set nor its forbidden list |
| Scope | Production source files whose stem carries a recognized layer prefix |
| Fix | Rename with an allowed suffix for the detected layer, or move the file |

#### Layer Suffix Policy

| Layer | Policy | Allowed Suffixes | Forbidden Suffixes |
| ----- | ------ | ---------------- | ------------------ |
| `root` | strict | `entry`, `container` | — |
| `taxonomy` | strict | `vo`, `entity`, `error`, `event`, `constant`, `request`, `response` | — |
| `contract` | strict | `protocol`, `aggregate` | — |
| `utility` | flexible | any | `vo`, `entity`, `error`, `event`, `constant`, `protocol`, `aggregate`, `request`, `response` |
| `capabilities` | flexible | any | `vo`, `entity`, `error`, `event`, `constant`, `constants`, `protocol`, `aggregate`, `utility`, `request`, `response` |
| `agent` | strict | `orchestrator` | — |
| `surface` | strict | `command`, `controller`, `page`, `view`, `component`, `router`, `layout`, `hook`, `store`, `action`, `screen` | — |

### AES103 — Test File Prefix

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when | `TEST_FILE_PREFIX`: a file in `tests/` or `benches/` is nested in a subdirectory, lacks a legal test-type prefix, or carries a prefix belonging to the other directory |
| Scope | `tests/` and `benches/` files only |
| Fix | Flatten the file into `tests/`/`benches/` and rename it `<type>_<subject>.<ext>` |

#### Legal Test Prefixes (with coverage role)

| Prefix | Directory | Proves |
| ------ | --------- | ------ |
| `contract_` | `tests/` | Protocol/trait/interface impl exists |
| `unit_` | `tests/` | One public function |
| `integration_` | `tests/` | Module / crate / package + DI wiring |
| `dogfood_` | `tests/` | CLI against live service/session; skip if unavailable |
| `smoke_` | `tests/` | App boots + responds |
| `e2e_` | `tests/` | Full request lifecycle |
| `acceptance_` | `tests/` | Business requirement met |
| `bench_` | `benches/` | Performance regression |
| support (`regression_`, `behavioral_`, `mock_`, `fixture_`) | `tests/` | auxiliary fixtures / regression markers |
| any | outside both dirs | no test-type prefix required |

---

## Group 2: Layer & Import Boundary (AES201–AES205)

Group 2 enforces layer dependency boundaries to maintain architectural integrity. The Import Matrix below is the canonical source for all allowed/mandatory/forbidden dependency rules.

### AES201 — Forbidden Import

| Field | Value |
| ----- | ----- |
| Severity | CRITICAL |
| Fires when | An import violates the allowed/mandatory/forbidden triple for the file's filename-prefix layer scope |
| Scope | Every scanned source file whose stem maps to one of the 13 layer scopes |
| Fix | Remove or redirect the import to a layer the scope's Allowed cell permits |

#### Import Matrix (13 Scopes)

| # | Scope | Allowed | Mandatory | Forbidden |
| - | ----- | ------- | --------- | --------- |
| 1 | `taxonomy(vo)` | `taxonomy` | — | `agent,surface,contract,utility,capabilities,root` |
| 2 | `taxonomy(request,response)` | `taxonomy` | — | `agent,surface,contract,utility,capabilities,root` |
| 3 | `taxonomy(entity,error,event)` | `taxonomy` | `taxonomy(vo|constant)` | `agent,surface,contract,utility,capabilities,root` |
| 4 | `taxonomy(constant)` | `taxonomy` | — | `agent,surface,contract,utility,capabilities,root` |
| 5 | `utility` | `taxonomy` | — | `agent,surface,contract,capabilities,root,utility` |
| 6 | `contract(protocol)` | `taxonomy,contract` | `taxonomy` | `agent,surface,capabilities,contract(aggregate),root` |
| 7 | `contract(aggregate)` | `taxonomy,contract` | `taxonomy` | `agent,surface,capabilities,root` |
| 8 | `capabilities` | `taxonomy,contract,utility` | `taxonomy,contract(protocol)` | `surface,agent,capabilities,root` |
| 9 | `agent(orchestrator)` | `taxonomy,contract(aggregate),contract(protocol),utility` | `taxonomy,contract(aggregate)` | `surface,capabilities,root` |
| 10 | `root` | `taxonomy,contract,capabilities,agent,surface` | — | — |
| 11 | `surface(command|controller|page)` | `taxonomy,contract(aggregate),utility` | — | `agent,capabilities,contract(protocol),root` |
| 12 | `surface(hook|store|action|screen|router)` | `taxonomy,contract(aggregate),utility` | — | `agent,capabilities,contract(protocol),surface(command|controller|page|entry),root` |
| 13 | `surface(component|view|layout)` | `taxonomy,contract(aggregate),utility` | — | `agent,contract,capabilities,surface(command|controller|page|entry|hook|store|action|screen|router),root` |

### AES202 — Mandatory Import

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when | A file is missing a required import defined by its layer's `mandatory` list |
| Scope | Every scanned source file whose layer declares a non-empty `mandatory` list |
| Fix | Add the required import statement |

### AES203 — Unused Import

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM |
| Fires when | A symbol is imported but never used in file scope (AST analysis across Rust, Python, JavaScript) |
| Fix | Remove the unused import or use the symbol |

### AES204 — Dummy Import

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when | An import string matches a forbidden dummy pattern — symbols used only inside `_use_mandatory_imports` dummy functions, dummy functions, or dummy trait impls |
| Fix | Use imported symbols in real logic, remove `_use_mandatory_imports` functions, implement contract methods with real behavior |

### AES205 — Circular Import

| Field | Value |
| ----- | ----- |
| Severity | CRITICAL |
| Fires when | A back-edge or cross-layer dependency cycle exists between layers |
| Fix | Extract shared types to taxonomy, define a contract protocol, or restructure dependency direction to bottom-up |

---

## Group 3: File & Content Quality (AES301–AES305)

Group 3 enforces file size limits and content quality standards to maintain code readability.

### AES301 / AES302 — File Line-Count Limits

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when (AES301) | File exceeds the maximum allowed line count (default: 1000) |
| Fix (AES301) | Split into smaller files |
| Fires when (AES302) | File is below the minimum required line count (default: 5) |
| Fix (AES302) | Merge into a related module or add more documentation |
| Scope | Every scanned source file; barrel/entry files and `*_constant` files are excepted |

### AES303 — Mandatory Definition

| Field | Value |
| ----- | ----- |
| Severity | HIGH (missing) / MEDIUM (empty) |
| Fires when | A source file has no struct/enum/trait/class definition, or a definition is empty |
| Scope | Every scanned source file; barrel/entry files, `*_constant.rs`, `*_constant.py`, `main.rs`, `main.py`, `py.typed` are excepted |
| Fix | Group functions into a struct or implement an interface; remove empty definitions |

#### Sub-checks

| # | Sub-check | Severity | Violation name | Fires when |
| - | --------- | -------- | -------------- | ---------- |
| 1 | Missing definition | HIGH | `MANDATORY_DEFINITION` | File has no struct/enum/trait/class at all |
| 2 | Empty / dead definition | MEDIUM | `DEAD_INHERITANCE` | `struct Foo;`, `impl X for Y {}`, `class Foo: pass`, `class Foo {}` |

### AES304 — Bypass Comment

| Field | Value |
| ----- | ----- |
| Severity | CRITICAL |
| Fires when | A forbidden bypass pattern is detected |
| Fix | Use proper error handling |

#### Forbidden Bypass Patterns

| Pattern | Violation kind |
| ------- | -------------- |
| `#[allow(...)]` | `BYPASS_COMMENT` |
| `unwrap()` / `expect()` | `UNWRAP_EXPECT` |
| `panic!` | `PANIC` |
| `todo` | `TODO` |
| `unimplemented` / `unreachable` | `UNIMPLEMENTED` |
| `noqa` / `type: ignore` / `eslint-disable` / `ts-ignore` / `ts-expect-error` | `BYPASS_COMMENT` |
| `FIXME` / `HACK` / `XXX` | `BYPASS_COMMENT` |
| `raise NotImplementedError` / `assert False` | `UNIMPLEMENTED` / `PANIC` |
| `throw new Error(...)` / `throw new TypeError(...)` / `throw new RangeError(...)` / `throw new ReferenceError(...)` / `throw new SyntaxError(...)` | `PANIC` |

### AES305 — Duplication Code

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM |
| Fires when | A file's share of shared normalized content windows exceeds the duplication threshold |
| Scope | Every scanned source file; import-only windows are excluded |
| Fix | Extract duplicated logic into shared utilities |

---

## Group 4: Role Violations (AES401–AES406)

Group 4 enforces role-specific constraints to ensure each layer maintains its intended responsibility. The layer reference tables below summarize each layer's purpose and rules; the per-rule cards that follow encode the violations.

### Layer Reference

#### Taxonomy (AES401)

| Aspect | Detail |
| ------ | ------ |
| Purpose | Domain foundation; stable domain language; free from technical/behavioral concerns |
| Roles | see AES102 Layer Suffix Policy |
| Rules | VOs and Constants may use primitives; entities/events/errors must use VOs/Constants instead (bool/str exception); constants must be compile-time; no business rules, infrastructure, or cross-layer imports |

#### Contract (AES402)

| Aspect | Detail |
| ------ | ------ |
| Purpose | Define public behavior without exposing implementation; stable interfaces |
| Roles | see AES102 Layer Suffix Policy |
| Rules | Protocol defines behavior only, without implementation; aggregate hides capabilities from Surface |

#### Capabilities (AES403)

| Aspect | Detail |
| ------ | ------ |
| Purpose | Concrete implementation of behavior; pure business logic + external adaptations |
| Role naming | Unlimited; chosen to describe technical responsibility |
| Rules | Never import other Capabilities; pipelines composed by Agent; shared technical mechanics extracted to Utility; must implement `protocol_`; own business/technical state; no domain model definitions |

#### Utility (AES404)

| Aspect | Detail |
| ------ | ------ |
| Purpose | Reusable low-level mechanics shared across capabilities |
| Role naming | Unlimited; chosen to describe technical responsibility |
| Location | Only in `shared/` (AES701); `utility_*` in a feature folder → AES702, in a surface folder → AES703 |
| Rules | Stateless standalone functions only; no stateful objects, behavior definitions, or contract impls; no business decisions |

#### Agent (AES405)

| Aspect | Detail |
| ------ | ------ |
| Purpose | Coordinate multiple capabilities into executable flows; control sequence and movement |
| Role | `orchestrator` only |
| Rules | Depend on Contract, never on concrete Capabilities; no business calculation; no domain model definitions |

#### Surface (AES406)

| Aspect | Detail |
| ------ | ------ |
| Purpose | Outer boundary; handles user/external-facing interaction; translates it into architectural actions |
| Allowed roles | see AES102 Layer Suffix Policy (`surface` row) |
| Rules | Smart surfaces consume Contract Aggregates; only smart surfaces import Utility; utility/passive surfaces must not import Capabilities/Contract/Agent; no business logic or orchestration |

#### Root

| Aspect | Detail |
| ------ | ------ |
| Purpose | Composition layer; assembles the system by connecting concrete implementations to contracts and starting the application |
| Roles | see AES102 Layer Suffix Policy (`root` row) |
| Rules | May instantiate and wire components; no business logic; no orchestration policy; no technical parsing or user-interface behavior |

### AES401 — Taxonomy Role

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when | `TAXONOMY_ROLE`: a `_constant` file carries a non-const declaration, or an `_entity`/`_error`/`_event` file uses a primitive type directly |
| Scope | Taxonomy files: `*_constant.rs`, `*_entity.rs`, `*_error.rs`, `*_event.rs` |
| Fix | Replace primitives with taxonomy value objects; keep `_constant` files const-only |

### AES402 — Contract Role

| Field | Value |
| ----- | ----- |
| Severity | HIGH |
| Fires when | `CONTRACT_ROLE`: a contract trait/method signature uses a primitive type instead of a taxonomy VO or constant |
| Scope | Contract files (`*_protocol.rs`, `*_aggregate.rs`); test projects are the primary target |
| Fix | Replace primitives with VO/constant types from the taxonomy layer |

### AES403 — Capabilities Role

| Field | Value |
| ----- | ----- |
| Severity | HIGH / MEDIUM / LOW per sub-check |
| Fires when | Capability violates protocol enforcement or the 3-block structure |
| Scope | Capability files (`*_capability*`); runs for Rust, Python, and TypeScript/JavaScript |
| Fix | Resolve each sub-check below |

#### Sub-checks

| #   | Sub-check               | Severity | Violation name    | Fires when                                                                     |
| --- | ----------------------- | -------- | ----------------- | ------------------------------------------------------------------------------ |
| 1   | CapabilityTooManyTypes  | HIGH     | `CAPABILITY_ROLE` | File exceeds max 3 type declarations                                           |
| 2   | CapabilityNoImplementor | MEDIUM   | `CAPABILITY_ROLE` | No struct/class implements a `_protocol` contract trait                        |
| 3   | CapabilityMultiProtocol | MEDIUM   | `CAPABILITY_ROLE` | File implements more than one protocol trait                                   |
| 4   | CapabilityBlockOrder    | HIGH     | `CAPABILITY_ROLE` | Block 2 (protocol trait impl) does not precede Block 3 (inherent impl)         |
| 5   | CapabilityBlockMarkers  | MEDIUM   | `CAPABILITY_ROLE` | `Block <n>:` banners missing, out of order, or above 3                         |
| 6   | CapabilityLocalConstant | MEDIUM   | `CAPABILITY_ROLE` | File-level `const` declared inline; belongs in `taxonomy_<domain>_constant.rs` |
| 7   | CapabilityEmbeddedTest  | LOW      | `CAPABILITY_ROLE` | `#[cfg(test)]` or `mod tests` declared inline                                  |
| 8   | CapabilityPublicHelper  | MEDIUM   | `CAPABILITY_ROLE` | Block 3 helper with no production caller is `pub`                              |

### AES404 — Utility Role

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM |
| Fires when | `UTILITY_ROLE`: a utility file contains stateful objects, struct/class state, trait definitions, impl blocks, type aliases, interface definitions, or enum definitions |
| Scope | Utility files (`*_utility*`) |
| Fix | Refactor to stateless standalone functions; remove non-taxonomy imports; move stateful logic into Capabilities |

### AES405 — Agent Role

| Field | Value |
| ----- | ----- |
| Severity | HIGH / MEDIUM / LOW per sub-check |
| Fires when | Agent orchestrator violates role discipline |
| Scope | Agent files (`*_orchestrator*`) |
| Fix | Resolve each sub-check below |

#### Sub-checks

| #   | Sub-check (dispatch order)       | Severity               | Violation name | Fires when                                                                                               |
| --- | -------------------------------- | ---------------------- | -------------- | -------------------------------------------------------------------------------------------------------- |
| 1   | `check_agent_routing`            | MEDIUM / HIGH / MEDIUM | `AGENT_ROLE`   | No aggregate-trait implementor (MEDIUM); >3 type declarations (HIGH); `Any`/`any` annotation (MEDIUM) |
| 2   | `check_agent_block_order`        | HIGH                   | `AGENT_ROLE`   | Block 2 does not precede Block 3                                                                         |
| 3   | `check_agent_protocol_forbidden` | HIGH                   | `AGENT_ROLE`   | Agent implements a contract protocol                                                                     |
| 4   | `check_agent_block_markers`      | MEDIUM                 | `AGENT_ROLE`   | `Block <n>:` banner with n > 3                                                                           |
| 5   | `check_agent_io_forbidden`       | MEDIUM                 | `AGENT_ROLE`   | Forbidden I/O operations in the agent file                                                               |
| 6   | `check_agent_constant_placement` | MEDIUM                 | `AGENT_ROLE`   | File-level constants; policy constants belong in taxonomy                                                |
| 7   | `check_agent_computation`        | MEDIUM                 | `AGENT_ROLE`   | `.sum()` / `.fold()` / `.reduce()` / arithmetic in agent file                                            |
| 8   | `check_agent_abstract_method`    | MEDIUM                 | `AGENT_ROLE`   | `@abstractmethod` in agent file                                                                          |
| 9   | `check_agent_stateless`          | MEDIUM                 | `AGENT_ROLE`   | State mutation outside the constructor                                                                   |
| 10  | `check_agent_free_fn`            | LOW                    | `AGENT_ROLE`   | Module-level free functions                                                                              |
| 11  | `check_agent_subsystem_count`    | LOW                    | `AGENT_ROLE`   | Fewer than 2 injected protocol subsystems                                                                |

### AES406 — Surface Role

| Field | Value |
| ----- | ----- |
| Severity | HIGH (one sub-check MEDIUM) |
| Fires when | A surface file carries too many responsibilities, active domain logic in a passive surface, or direct surface-to-domain calls |
| Scope | Surface files (suffix set: see AES102 Layer Suffix Policy, `surface` row) |
| Fix | Split surface responsibilities; move business logic to Capabilities; route domain calls through contracts |

#### Sub-checks

| #   | Sub-check                              | Severity | Violation name | Fires when                                                                  |
| --- | -------------------------------------- | -------- | -------------- | --------------------------------------------------------------------------- |
| 1   | Function-count ceiling (tier-specific) | HIGH     | `SURFACE_ROLE` | Smart exempt; utility 25; passive surface exceeds MAX_PUBLIC_METHODS (50) |
| 2   | Active domain logic in passive surface | HIGH     | `SURFACE_ROLE` | Passive surface carries business logic                                      |
| 3   | Surface logic bypass                   | MEDIUM   | `SURFACE_ROLE` | Surface calls domain logic directly (`lint_path(`, `walk_rs_files(`)        |

---

## Group 5: Orphan Code (AES501–AES506)

Group 5 detects orphaned code that is not wired into the system's composition layer. A file is orphaned when no other layer imports or references it; the composition root's container/entry files are the wiring point.

### Orphan Rules

| Code | Layer | Fires when | Scope | Fix |
| ---- | ----- | ---------- | ----- | --- |
| AES501 | Taxonomy | A taxonomy file (VO, entity, error, event, constant) has no inbound imports from any contract file | Taxonomy files | Wire the taxonomy type into a contract, or remove the dead taxonomy file |
| AES502 | Contract | A contract protocol is not implemented by any capabilities file, or a contract aggregate is not implemented by any agent file; not imported by any container or entry point | Contract files (`*_protocol*`, `*_aggregate*`) | Implement the protocol/aggregate, or wire it into a container; barrel re-exports do not count |
| AES503 | Capabilities | A capability file is not wired in any `_container` | Capability files | Wire the capability into a container |
| AES504 | Utility | A utility file is not imported or consumed by any capability, agent, surface, or root file, or is only imported by other utility files | Utility files | Import the utility from a capability/agent/surface/root file, or remove it |
| AES505 | Agent | An agent orchestrator file (suffix `_orchestrator`) is not wired in any `_container` | Agent orchestrator files | Wire the orchestrator into a container |
| AES506 | Surface | A surface file is not imported by its required consumer; severity depends on surface category | Surface files (suffix set: see AES102 Layer Suffix Policy, `surface` row) | Import the surface from its required consumer |

### AES506 Category / Severity / Consumer

| Category | Severity    | Must be imported by      |
| -------- | ----------- | ------------------------ |
| Smart    | HIGH        | entry                    |
| Utility  | MEDIUM      | smart surface            |
| Passive  | LOW         | smart or utility surface |
| `_entry` | never fires | —                        |

---

## Group 6: Document Invariants (AES601–AES610)

Group 6 enforces document structure, cross-reference integrity, and template conformance across the ten recognized spec documents.

### Shared invariants (apply to every AES6xx rule below)

| Invariant | Fires when |
| --------- | ---------- |
| Line drift | A non-placeholder line of the document's own template was edited away from its scaffolded shape |
| Heading structure | Zero or >1 H1; a required H2 is absent; an H2 outside required ∪ allowed |
| Crosslinks | Reference section is missing one of the document's required link targets |

The table below lists only the **doc-specific** invariants. Every row also answers the three shared invariants above with the doc's own AES stamp. "Entry carries aspect H4s" means the entry section holds its per-aspect H4 subsections, in order, with at least the seed-minimum rows.

### Document × Invariant

| Code   | Document          | Reference links                                                                  | Specific invariants                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------ | ----------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AES601 | `AGENTS.md`       | `README`, `CONTRIBUTING`, `ARCHITECTURE`, `ROADMAP`, `PRD`                       | YAML frontmatter; `Runtime` entry table carries all `AGENTS_RUNTIME_ROW_LABELS` rows; `Commands` entry table carries all `AGENTS_COMMAND_COLUMNS`                                                                                                                                                                                                                                                                                                                                                  |
| AES602 | `README.md`       | —                                                                                | `Quick Start` table carries all `README_QUICK_START_COLUMNS`                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| AES603 | `ARCHITECTURE.md` | —                                                                                | — (shared invariants only)                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| AES604 | `CONTRIBUTING.md` | `PRD`, `ARCHITECTURE`                                                            | `Workflow` table carries `CONTRIBUTING_WORKFLOW_COLUMNS`; `Commit Convention` table carries `CONTRIBUTING_COMMIT_COLUMNS`                                                                                                                                                                                                                                                                                                                                                                          |
| AES605 | `PRD.md`          | `ROADMAP`, `ARCHITECTURE`                                                        | PR-ID parity with `ROADMAP`; promised API methods exist in contract; `Project Requirements` entry carries aspect H4s `User Stories`, `Proposed Solution`, `Main User Flow`                                                                                                                                                                                                                                                                                                                         |
| AES606 | `ROADMAP.md`      | `PRD`, `ARCHITECTURE`                                                            | PR-ID parity with `PRD`; `Roadmap Status` entry row labels match `ROADMAP_ROW_LABELS`; cross-cutting `missing_member_doc`/`forbidden_member_doc`/`missing_required_doc` stamped here                                                                                                                                                                                                                                                                                                               |
| AES607 | `BACKLOG.md`      | role-aware: `PRD`, `ARCHITECTURE`, `ROADMAP`, plus `FRD`/`DATA`/`DESIGN` by role | BACKLOG qualifier alignment against paired spec union (FRD/DATA/DESIGN by role, or root PRD/ROADMAP); `Backlog Status` entry carries aspect H4s                                                                                                                                                                                                                                                                                                                                                    |
| AES608 | `DATA.md`         | `PRD`, `BACKLOG`, `ROADMAP`, `ARCHITECTURE`                                      | DT-ID format `DT-<NAME>-NNN`; spec purity (no source files, no status); `DT-` item H2s allowed; `Data Requirements` entry carries aspect H4s                                                                                                                                                                                                                                                                                                                                                       |
| AES609 | `FRD.md`          | `PRD`, `BACKLOG`, `ROADMAP`, `ARCHITECTURE`                                      | FR-ID format `FR-<NAME>-NNN`; FR protocol parity (`I*Protocol` count = FRD requirement count, `I*Aggregate` excluded); promised API methods exist in contract; spec purity (as AES608); section order `Feature Overview → Functional Requirements → Public Interface → Reference` with `Protocol API` then `Aggregate API`; `Functional Requirements` entry carries 6 `Technical Specification` rows (`Input`, `Output`, `Protocol`, `Method`, `Event`, `Error`); `API Contract` legacy H2 allowed |
| AES610 | `DESIGN.md`       | `PRD`, `BACKLOG`, `ROADMAP`, `ARCHITECTURE`                                      | DS-ID alignment with `BACKLOG`; H3 sweep (Design Overview and Reference sanction no H3; Design Requirements sanctions only `DS-`-prefixed H3s); no table outside template; `Design Requirements` entry carries aspect H4s                                                                                                                                                                                                                                                                          |

---

## Group 7: Folder Structure (AES701–AES706)

Group 7 enforces folder structure invariants to maintain vertical slicing and layer purity.

### Terms

| Term | Meaning |
| ---- | ------- |
| Project Workspaces | Project root containing all configuration and language members |
| Workspace Member | One self-contained crate, package, or module inside the workspace |
| Crates directory | Rust workspace members |
| Packages directory | TypeScript or JavaScript packages |
| Modules directory | Python modules |

### Vertical Slicing Layout

AI agents frequently make this mistake: do NOT create `surface/`, `taxonomy/`, `contract/`, `capabilities/`, `utility/`, `agent/` folders. The correct structure groups files by feature, with layers as filenames, not directories.

### General Layout

```text
project-root/
├── crates|packages|modules/
│   ├── shared/
│   ├── <feature-a>/
│   ├── <feature-b>/
│   ├── <surface-a>/
│   └── <surface-b>/
├── Cargo.toml / package.json / pyproject.toml
```

### Member Types

| Member Type | Example Path | Carries | Belongs in | Documents |
| ----------- | ----------- | ------- | ---------- | --------- |
| Features | `crates/<name-features>/` | `capabilities_*` + `agent_*_orchestrator` | a feature folder | `FRD.md` + `BACKLOG.md` |
| Surface | `crates/<name-surfaces>/` | `surface_*` | a surface folder | `DESIGN.md` + `BACKLOG.md` |
| Shared | `crates/shared/<domain>/` | `contract_*` + `taxonomy_*` + `utility_*` | the shared folder | `DATA.md` + `BACKLOG.md` |

### AES701 — Shared Folder Purity

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM (report) |
| Fires when | A shared folder holds a `capabilities_*`, `agent_*`, or `surface_*` file (`shared_has_forbidden_files`), or lacks its DATA.md + BACKLOG.md doc pair (`shared_missing_doc_pair`) |
| Scope | `shared/` layer folders under member dirs |
| Fix | Move misplaced layer files to a feature or surface folder; add DATA.md and BACKLOG.md |

### AES702 — Feature Folder Health

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM (report) |
| Fires when | `feature_missing_agent` (capabilities but no orchestrator), `feature_missing_capability` (orchestrator but no capabilities), `feature_has_forbidden_files` (foreign layer file), `feature_missing_doc_pair` (no FRD.md/BACKLOG.md), `feature_missing_root_container` (no `root_*` composition), `feature_missing_shared_subfolder` (no `shared/src/<feature>/` mirror), `doc_pair_without_orchestrator` |
| Scope | Member subdirectories (`crates/`, `modules/`, `packages/`) |
| Fix | Add the missing orchestrator/capabilities file, remove foreign files, add the doc pair, add a `root_*` composition file, or mirror into `shared/src/<feature>/` |

### AES703 — Surface Folder Purity

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM (report) |
| Fires when | `surface_has_misplaced_files` (holds a `capabilities_*`, `agent_*`, or `utility_*` file), `surface_missing_design_md`, or `surface_missing_backlog_md` |
| Scope | Surface-dominated folders under member dirs |
| Fix | Move capability/agent/utility files out; add DESIGN.md and BACKLOG.md |

### AES704 — Test Suite Coverage

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM (report) |
| Fires when | `test_suite_missing_tests_dir`, `test_suite_missing_bench_dir`, or `test_suite_missing_category` (no file carries a required test prefix) |
| Scope | Folders owning `capabilities_*` or `agent_*_orchestrator` source |
| Fix | Add missing test files/benches with one of the required prefixes (see AES103 Legal Test Prefixes) plus a `bench_` file |

### AES705 — Member-Root Placement

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM (report) |
| Fires when | A member dir (`crates/`, `modules/`, `packages/`) root holds a `capabilities_*`, `agent_*`, `surface_*`, or `utility_*` file |
| Scope | Member root level only |
| Fix | Move the layer file per Member Types "Belongs in" (see above) |

### AES706 — PR Folder Mapping

| Field | Value |
| ----- | ----- |
| Severity | MEDIUM (report) |
| Fires when | `pr_la_missing_frd` (a module folder holds no FRD.md), `pr_la_fr_id_mismatch` (a module folder's FRD carries an FR id whose prefix does not match the folder name), or `pr_la_id_mismatch` (a `PR-LA-001..N` id does not map to an existing crate folder by order) |
| Scope | `PRD.md`, `ROADMAP.md`, and feature module folders under `crates/` / `modules/` / `packages/` |
| Fix | Create the missing module folder, rename mismatched FR ids to `FR-<Feature>-NNN`, or add the missing FRD.md |
