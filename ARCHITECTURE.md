# Agentic Engineering System Architecture

## 1. Purpose

The Agentic Engineering System is a layered, AI-native architecture pattern. It keeps domain models stable, business logic readable, technical detail isolated, and layer boundaries explicit enough for both humans and AI agents to modify the system safely.

---

## 2. Workspace Organization

The architecture supports multi-language workspaces.

| Term               | Meaning                                                           |
| ------------------ | ----------------------------------------------------------------- |
| Project Workspaces | Project root containing all configuration and language members    |
| Workspace Member   | One self-contained crate, package, or module inside the workspace |
| Crates directory   | Rust workspace members                                            |
| Packages directory | TypeScript or JavaScript packages                                 |
| Modules directory  | Python modules                                                    |

---

## 3. Naming Convention

File names must communicate three parts:

1. Layer as prefix
2. Concern as middle name
3. Role as suffix

The parts are joined by underscores, followed by the normal file extension for the language.

`layer_concern_role.rs/py/ts`

---

## 4. Vertical Slicing Folder Structure

AI agents frequently make this mistake. Do NOT create `surface/`, `taxonomy/`,
`contract/`, `capabilities/`, `utility/`, `agent/` folders. The correct structure
groups files by feature, with layers as filenames, not directories.

#### Features member

A workspace member is a feature only when its tree contains an
`agent_*_orchestrator` file. Every such member carries sibling `FRD.md` and
`BACKLOG.md` documents at the member root. Members without an orchestrator —
including surface-only and shared members — carry neither document.

_Example feature crate `crates|packages|modules/<name-features>/`_

```text
surface_<concern>_<role>.rs/py/ts                ← surface layer
utility_<concern>_<role>.rs/py/ts                ← utility layer
capabilities_<concern>_<role>.rs/py/ts           ← capabilities layer
agent_<concern>_orchestrator.rs/py/ts            ← agent layer
```

Exceptions: `main.rs`, `lib.rs`, `mod.rs`, `__init__.py`, `index.ts`, `index.js`.

#### Shared member

`crates|packages|modules/shared/<common>or<domain-folder>`

```text
contract_<concern>_protocol.rs/py/ts             ← contract layer
contract_<concern>_aggregate.rs/py/ts            ← contract layer
taxonomy_<concern>_vo.rs/py/ts                   ← taxonomy layer
taxonomy_<concern>_event.rs/py/ts                ← taxonomy layer
taxonomy_<concern>_entity.rs/py/ts               ← taxonomy layer
taxonomy_<concern>_constant.rs/py/ts             ← taxonomy layer
```

`shared` folder groups by domain. Use `shared/common/` for generic files.

### General Workspace Layout

```
project-root/                             <- Project workspace root
│
├── crates|packages|modules/              <- workspace members
│   ├── shared/                           <- SHARED: Taxonomy + Contract (all features)
│   │   └── src/
│   │       ├── taxonomy_<domain>_vo.rs/py/ts 
│   │       ├── taxonomy_<domain>_entity.rs/py/ts 
│   │       ├── taxonomy_<domain>_event.rs/py/ts 
│   │       ├── taxonomy_<domain>_error.rs/py/ts 
│   │       ├── taxonomy_<domain>_constant.rs/py/ts 
│   │       ├── contract_<domain>_protocol.rs/py/ts 
│   │       └── contract_<domain>_aggregate.rs/py/ts 
│   │
│   ├── <feature-a>/                      <- FEATURE: <feature-a description>
│   │   └── src/
│   │       ├── agent_<feature-a>_orchestrator.rs/py/ts         <- Agent
│   │       ├── capabilities_<feature-a>_<role>.rs/py/ts        <- Capabilities
│   │       ├── capabilities_<feature-a>_<role>.rs/py/ts        <- Capabilities
│   │       ├── utility_<feature-a>_<role>.rs/py/ts             <- Utility
│   │       ├── utility_<feature-a>_<role>.rs/py/ts             <- Utility
│   │       ├── root_<feature-a>_container.rs/py/ts            <- Root
│   │       └── lib.rs
│   │
│   ├── <feature-b>/                      <- FEATURE: <feature-b description>
│   │   └── src/
│   │       ├── agent_<feature-b>_orchestrator.rs/py/ts         <- Agent
│   │       ├── capabilities_<feature-b>_<role>.rs/py/ts        <- Capabilities
│   │       ├── utility_<feature-b>_<role>.rs/py/ts             <- Utility
│   │       ├── root_<feature-b>_container.rs/py/ts             <- Root
│   │       └── lib.rs
│   │
│   ├── <surface-c>/                      <- NON-FEATURE: surface-only member
│   │   └── src/
│   │       ├── surface_<surface-c>_<role>.rs/py/ts             <- Surface
│   │       └── lib.rs
│   │
│   └── ...
│
│
├── Cargo.toml                    
├── package.json
└── pyproject.toml
```

---

## 5. Taxonomy Layer

### Purpose

Taxonomy is the domain foundation layer. It defines the stable language of the domain and must remain free from technical or behavioral concerns.

### Components

| Role         | Meaning                               |
| ------------ | ------------------------------------- |
| Value object | Immutable data concept                |
| Entity       | Stateful domain concept with identity |
| Event        | Immutable domain fact                 |
| Error        | Domain-level error                    |
| Constant     | Compile-time literal value            |

### Dependencies

Taxonomy depends on nothing.

### Special Rules

- Value objects and Constants may use all primitive types.
- Entities, Events, and Errors must use Value objects/Constants instead of primitive types (bool/str is an exception).
- Constants must be compile-time values.
- Taxonomy must not contain business rules, infrastructure, or imports from other layers.

---

## 6. Contract Layer

### Purpose

Contract defines the public behavior of the system without exposing implementation. It allows callers to depend on stable interfaces instead of concrete logic.

### Components

| Role      | Meaning                                                                                           |
| --------- | ------------------------------------------------------------------------------------------------- |
| Protocol  | Interface defining inbound behavior. It is implemented by Capabilities and consumed by the Agent. |
| Aggregate | Facade definition implemented by Agent, used by Surface to access feature behavior.               |

### Dependencies

Contract may depend on Taxonomy only.

### Special Rules

- Protocol defines behavior only without implementation.
- Aggregate hides Capabilities from Surface.

---

## 7. Utility Layer

### Purpose

Utility contains reusable low-level mechanics that can be shared cross capabilities. It exists so that Capabilities can remain clean.

### Role Naming

Utility role suffixes are unlimited. The role name is chosen based on demand and must describe the technical responsibility and concern of the file.

### Dependencies

Utility may depend only on Taxonomy.

### Technical Concern Examples

| Concern                 | Responsibility                                      |
| ----------------------- | --------------------------------------------------- |
| File discovery          | Walk directories, detect files, apply ignore        |
| External tool execution | Run linters, compilers, formatters, analyzers       |
| Parsing and matching    | Parse text, match patterns, extract structured data |
| Path normalization      | Normalize paths across platforms                    |
| System operations       | Handle process or environment mechanics             |

### Special Rules

- Utility must use stateless standalone functions only.
- Utility must not contain stateful objects, behavior definitions, or contract implementations.
- Utility must not make business decisions.
- Utility may perform technical operations if needed.
- Utility must not implement any contract.
- Utility role names may expand freely, but the layer must remain technical and standalone.
- Utility must use stateless standalone functions only.

---

## 8. Capabilities Layer

### Purpose

Capabilities contain the concrete implementation of the system's behavior. This layer encapsulates both **pure business logic** (computations, validations) and **external adaptations** (database access, third-party API calls, infrastructure mechanics). By hiding these implementations behind Contracts, the system keeps its behavior modular, swappable, and fully isolated from orchestration.

### Role Naming

Capabilities role suffixes are unlimited. The role name is chosen based on demand and must describe the technical responsibility and concern of the file.

### Dependencies

- Capabilities may depend on Taxonomy, Contract, and Utility.
- Capabilities must not depend on or import other Capabilities.

### Concern Examples

Capabilities generally handle two types of concerns:

| Category                      | Concern        | Responsibility                                 |
| ----------------------------- | -------------- | ---------------------------------------------- |
| **Business Logic**      | Validation     | Check domain conditions or input correctness   |
|                               | Computation    | Calculate scores, totals, or derived values    |
|                               | Transformation | Map, filter, reduce, or reshape data           |
|                               | Resolution     | Apply rules and decide outcomes                |
|                               | Assessment     | Judge severity, compliance, grade, or quality  |
| **External Adaptation** | Repository     | Fetch or persist domain entities to a database |
|                               | Integration    | Communicate with third-party services or APIs  |
|                               | Provider       | Generate data from external systems            |

### Special Rules

- **No Inter-Capability Dependency:** Capabilities must never import or call other Capabilities directly. They are standalone execution units.
- **Pipeline Aggregation:** Multiple Capabilities (e.g., Capability A for data fetching, Capability B for business calculation) are designed to be composed into a sequential pipeline by the **Agent Layer**, not by themselves.
- **Shared Logic Extraction (DRY):** If multiple Capabilities require the same technical mechanics or functions, that logic must be extracted into a reusable standalone function in the **Utility Layer**. Capabilities must not duplicate technical code (Don't Repeat Yourself).
- **Contract Implementation:** Capabilities must implement the `protocol_` defined in the Contract Layer.
- **State Ownership:** Capabilities are the owners of business and technical state within their execution scope.
- **No Domain Definition:** Capabilities must not define domain models (Entities, Value Objects); they only consume Taxonomy.

---

## 9. Agent Layer

### Purpose

Agent coordinates multiple capabilities into executable flows. It controls sequence and movement, not business calculation.

### Allowed Role

The only Agent role is orchestrator.

### Dependencies

Agent may depend only on Taxonomy, Contract, and Utility.

### Allowed Flow Control

| Flow Type               | Purpose                                |
| ----------------------- | -------------------------------------- |
| Sequential execution    | Run steps in order                     |
| Looping                 | Process multiple items or events       |
| Branching               | Choose path based on result            |
| Error handling          | Recover, abort, continue, or escalate  |
| Timeout or cancellation | Stop long-running or asynchronous work |

### Special Rules

- Agent must depend on Contract, not concrete implementations.
- Agent must not use and must be completely ignorant of Capabilities implementations.
- Agent must not calculate business results.
- Agent must not define domain models.

---

## 10. Surface Layer

### Purpose

Surface is the outer boundary of the system. It handles user-facing or external-facing interaction and translates it into architectural actions.

### Allowed Roles

Surface roles include:

- command
- controller
- page
- view
- component
- router
- layout
- hook
- store
- action
- screen

### Surface Groups

| Group            | Roles                             | Allowed Dependencies                | Forbidden Dependencies                                     | Rule                                           |
| ---------------- | --------------------------------- | ----------------------------------- | ---------------------------------------------------------- | ---------------------------------------------- |
| Smart surfaces   | command, controller, page, router | Taxonomy, Contract Aggregate, Utility | Agent, Capabilities, Contract Protocol, Root              | May initiate feature behavior through aggregate |
| Utility surfaces | hook, store, action, screen       | Taxonomy                            | Agent, Capabilities, Contract, Utility, Other surfaces, Root | Support smart surfaces, data/state only         |
| Passive surfaces | component, view, layout           | Taxonomy                            | Agent, Contract, Capabilities, Other surfaces, Root        | Presentation-only, no logic or orchestration    |

### Special Rules

- Smart surfaces must consume Contract Aggregates to reach capabilities/agent.
- Only smart surfaces may import Utility layer files.
- Utility and passive surfaces must not import Capabilities, Contract, or Agent directly.
- Surfaces must not contain business calculation or orchestration.

---

## 11. Root Layer

### Purpose

Root is the composition layer. It assembles the system by connecting concrete implementations to contracts and starting the application.

### Components

| Role      | Meaning                                                                           |
| --------- | --------------------------------------------------------------------------------- |
| Container | Wires one feature by connecting Capabilities to Contract protocols and aggregates |
| Entry     | Bootstraps the application and composes feature containers                        |

### Dependencies

Root may depend on all layers.

### Special Rules

- Root may instantiate and wire components.
- Root must not contain business logic.
- Root must not contain orchestration policy.
- Root must not contain technical parsing or user interface behavior.
