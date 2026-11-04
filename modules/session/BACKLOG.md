# BACKLOG — Session Feature

FRD: [FRD.md](FRD.md)
Architecture: [ARCHITECTURE.md](../../ARCHITECTURE.md)
State: values from root [ROADMAP.md](../../ROADMAP.md).
Last Updated: 2026-10-25

## Progress Overview

The session feature is Done. `uv run python -m pytest modules/session/tests/ -v` → 147 passed (2026-10-25) covers pool keep/rotate, authentication, rate-limit detection, rotation, renewal, and profile preparation. No row is in progress or blocked; every backlog entry is Done.

## Backlog Status

### FR-Session-001

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/session/tests/unit_capabilities_session_manager.py -v` → 24 passed (2026-10-25, commit `e4f5341`). A backup write failure refuses the deletion and leaves the master profile in place. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-Session-002

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/session/tests/ -v` → 147 passed (2026-10-25, commit `03d72dc`). Authentication verifies a live auth session before the pipeline runs. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-Session-003

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/session/tests/unit_capabilities_session_rotator.py -v` covers the throttle path; every pooled session rate-limited reports the throttle. Evidence `uv run python -m pytest modules/session/tests/ -v` → 147 passed (this commit). |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-Session-004

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/session/tests/unit_agent_session_orchestrator.py -v` covers rotation: the rotator selects the next healthy session, skipping already-tried and rate-limited ones; an exhausted pool returns the reasoned `no_eligible_session` outcome. Evidence `uv run python -m pytest modules/session/tests/ -v` → 147 passed. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-Session-005

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/session/tests/ -v` → 147 passed (2026-10-25). A stale auth session is renewed transparently via the refresh-token flow; renewal failure raises `AuthRequiredError` so the caller falls back to manual login. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-Session-006

| Aspect | Detail |
| --- | --- |
| State | Done |
| Done | `uv run python -m pytest modules/session/tests/ -v` → 147 passed (2026-10-25). The profile preparer owns the mode→clone decision: login mode yields the master path, every other mode yields an ephemeral clone so concurrent browser processes never hit a SingletonLock conflict. |
| In Progress | None |
| Risk | None |
| Updated | 2026-10-25 |

### FR-Session-007: Brave session sourcing

| Aspect | Detail |
| --- | --- |
| State | In Progress |
| Done | `modules/shared/src/session/utility_session_brave_paths.py` — Brave path constants + `find_brave_profiles()` scanner with `brave_profile_name()` and `is_brave_profile_path()`. Marker detection reconciled: root-level `Cookies` (regular Brave profiles) accepted alongside `Default/Cookies` and `Local State`. |
| | `modules/shared/src/session/taxonomy_session_brave_vo.py` — `BraveProfileInfo` frozen dataclass (path, name, source, is_regular_browser, is_web_app_hub). |
| | `modules/session/src/capabilities_session_brave_discovery.py` — `SessionBraveDiscovery` implementing `ISessionBraveDiscoveryProtocol`; best-effort, never raises. |
| | `modules/session/tests/unit_capabilities_session_brave_discovery.py` — unit tests (empty when no brave dirs, finds profiles, reads names). |
| | `modules/session/tests/integration_session_brave_import.py` — integration test: fake Brave profile, import via SessionManager, verify pool entry + ephemeral clone. |
| | `modules/shared/src/session/contract_session_protocol.py` — `ISessionBraveDiscoveryProtocol` added; `brave_profile_path` field on `SessionRequest`; `brave_profiles` on `SessionResponse`. |
| | `modules/shared/src/session/taxonomy_session_vo.py` — `brave_profile_path` and `brave_profiles` fields; `BraveProfileInfo` in `__all__`. |
| | `modules/session/src/capabilities_session_manager.py` — `register_brave_profile`, `discover_brave_profiles`, `is_brave_profile`; constructor takes `brave_discovery`. |
| | `modules/session/src/capabilities_session_profile_preparer.py` — Brave master always cloned to ephemeral even in login mode. |
| | `modules/session/src/agent_session_orchestrator.py` — verbs `brave_list`/`brave_import`; `_validate_saved_session` skips renewal on Brave paths. |
| | `modules/cli/src/surface_cli_sessions_command.py` — `brave-list` and `brave-import` subcommands + handlers. |
| | `modules/root_core_container.py` — `BraveProfileDiscovery` constructed and injected into `SessionManager` and `SessionOrchestrator`. |
| | `modules/session/FRD.md` — FR-Session-007 added. |
| In Progress | `uv run python -m pytest modules/session/tests/ -q`; `ruff check modules`; `mypy modules`; commit on `brave/session-sourcing`. |
| Risk | None |
| Updated | 2026-11-04 |

## Reference

| Artifact | Purpose | Link |
| --- | --- | --- |
| PRD | Business goals and scope | [PRD.md](../../PRD.md) |
| FRD | Functional requirements specification | [FRD.md](FRD.md) |
| Roadmap | Timeline, phasing, and dependencies | [ROADMAP.md](../../ROADMAP.md) |
| Architecture | System boundaries, tech stack, and infra | [ARCHITECTURE.md](../../ARCHITECTURE.md) |
