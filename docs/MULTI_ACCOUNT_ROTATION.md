# Multi-Account Rate Limit Rotation System

## Policy Gate (2026-10-18, Raka / project owner)

**Provider policy decision:** Quota-triggered cross-account rotation on authorized accounts is permitted. All configured accounts must be accounts the operator owns and controls. This decision was recorded 2026-10-18 with approver Raka, project owner.

Rules:
- Quota-triggered rotation across owned/authorized accounts is approved and supported.
- A CAPTCHA or any provider access-control stop halts immediately with no bypass attempt.
- Reduce-throughput remains the documented non-rotation recovery guidance.
- Do not represent the feature as unapproved; it is the approved boundary described above.
- Unconditional "add more accounts" recovery advice is removed; state the authorized-accounts-only rule instead.

## Problem Statement

Qwen API has daily usage limits. When a session hits the limit, all subsequent requests fail with:
```
Oops! There was an issue connecting to Qwen3.8-Max.
You've reached the upper limit for today's usage. Please try again tomorrow.
```

This blocks:
- Swarm execution (multiple roles fail)
- Long-running pipelines
- Batch processing

## Solution: Multi-Account Rotation System

### Core Concepts

1. **Session Pool**: Multiple Qwen login sessions stored and managed
2. **Health Check**: Quick ping test to detect rate limits before expensive operations
3. **Quota-triggered rotation**: When a session hits its daily limit, rotation moves to the next authorized session in the pool
4. **Fallback Chain**: Try Session 1 → Session 2 → Session 3 until success; if all are limited, return an explicit `no_eligible_session` outcome before submitting

### Policy gate

See the [Policy Gate](#policy-gate-2026-10-18-raka--project-owner) section at the top of this document for the approved boundary and its rules. The rotation logic below implements it: no submission through a known-LIMITED profile, and a CAPTCHA or access-control stop halts immediately.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI / TUI / MCP                         │
│                      (User Interface)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              SessionRotatorAggregate                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Session 1  │  │  Session 2  │  │  Session 3  │  ...    │
│  │  (Active)   │  │  (Backup)   │  │  (Backup)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Health Checker (Ping Test)                │   │
│  │  - Send "ping" → expect "pong"                      │   │
│  │  - < 5s timeout                                    │   │
│  │  - Detect rate limit response                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Rotation Logic                            │   │
│  │  - Track failed sessions                            │   │
│  │  - Round-robin fallback                             │   │
│  │  - Auto-heal on success                             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Session Storage Layer                           │
│  ~/.local/share/qwen-web-arwaky/sessions/                                      │
│  ├── session_1/  ( Chromium profile )                       │
│  ├── session_2/  ( Chromium profile )                       │
│  └── session_3/  ( Chromium profile )                       │
└─────────────────────────────────────────────────────────────┘
```

### Data Model

```python
@dataclass
class SessionInfo:
    session_id: str  # "session_1", "session_2", etc.
    path: Path  # ~/.local/share/qwen-web-arwaky/sessions/session_1/
    status: SessionStatus  # active, limited, auth_required
    last_used: datetime | None
    total_requests: int = 0
    failed_requests: int = 0


class SessionStatus(str, Enum):
    ACTIVE = "active"  # Healthy, can send requests
    LIMITED = "limited"  # Hit rate limit
    AUTH_REQUIRED = "auth_required"  # Authentication required or probe failure
    UNKNOWN = "auth_required"  # Read-only alias for legacy pool files; the next save_pool rewrites it as "auth_required"


@dataclass
class SessionPool:
    sessions: list[SessionInfo]
    current_index: int = 0

    def get_next_session(self) -> SessionInfo:
        """Round-robin with fallback to healthy sessions."""
        ...

    def mark_limited(self, session_id: str, reason: str = "QUOTA") -> None:
        """Mark session as rate-limited; a None reason normalises to "QUOTA"."""
        ...

    def mark_healthy(self, session_id: str) -> None:
        """Mark session as healthy after successful request."""
        ...
```

### Session Management Commands

```bash
# List all sessions
qwen-web-arwaky session list

# Add a new session (via login)
qwen-web-arwaky session login --name "personal"

# Remove a session
qwen-web-arwaky session remove session_2

# Test session health (ping test)
qwen-web-arwaky session health

# Show rotation status
qwen-web-arwaky session status
```

### Ping Test Implementation

```python
class SessionLoginChecker:
    """Quick health check using minimal ping message (login verdict: ACTIVE or AUTH_REQUIRED)."""
    
    PING_MESSAGE = "Reply with just: pong"
    EXPECTED_RESPONSE = "pong"
    TIMEOUT_SECONDS = 5
    
    async def check_session(self, session: SessionInfo) -> SessionHealthResult:
        """Returns a verdict: ACTIVE when the session is authenticated, AUTH_REQUIRED otherwise."""
        try:
            result = await self._send_ping(session)
            return self._is_authenticated(result)
        except Exception:
            return AUTH_REQUIRED


class SessionLimitChecker:
    """Rate-limit verdict (ACTIVE or LIMITED) using minimal ping message."""

    PING_MESSAGE = "Reply with just: pong"
    EXPECTED_RESPONSE = "pong"
    TIMEOUT_SECONDS = 5

    async def check_session(self, session: SessionInfo) -> SessionHealthResult:
        """Returns a verdict: ACTIVE when the page is healthy, LIMITED when rate-limited."""
        try:
            result = await self._send_ping(session)
            return self._is_healthy(result)
        except Exception:
            return LIMITED

    async def _send_ping(self, session: SessionInfo) -> str:
        """Send minimal ping and capture response."""
        # Use lightweight browser context
        # Send "Reply with just: pong"
        # Wait up to 5 seconds
        # Return response text
        ...
    
    def _is_healthy(self, response: str) -> bool:
        """Detect rate limit in response."""
        rate_limit_signals = [
            "upper limit",
            "rate limit",
            "daily limit",
            "Please try again tomorrow",
            "quota exceeded",
        ]
        response_lower = response.lower()
        return not any(signal in response_lower for signal in rate_limit_signals)
```

### Rotation Logic

```python
class SessionRotator:
    """Session rotation for API calls with quota-triggered rotation."""

    def __init__(self, session_pool: SessionPool):
        self.pool = session_pool
        self.failed_sessions: set[str] = set()

    async def rotate(self, request: RotatorRequest) -> RotatorResponse:
        """Return the next eligible session or an explicit no_eligible_session outcome.

        - Skips sessions already tried in this turn (request.exclude_ids).
        - Uses diagnosed health verdicts (ACTIVE, LIMITED, AUTH_REQUIRED).
        - Never submits through a known-LIMITED profile.
        - When no eligible session remains, returns RotatorResponse(outcome="no_eligible_session")
          with reason ("all_sessions_limited" / "empty_pool" / "all_sessions_excluded").
        """
        pool = self.pool
        if not pool.sessions:
            return RotatorResponse(
                session=None,
                outcome="no_eligible_session",
                reason="empty_pool",
                recovery_action=(
                    "No sessions configured. Run 'qwen-web-arwaky session login --name <name>' "
                    "to add an authorized session."
                ),
            )

        excluded = set(request.exclude_ids)

        for candidate in pool.sessions:
            if candidate.session_id in excluded:
                continue
            verdict = await self.limit_checker.check_session(candidate)
            if verdict.is_healthy:
                return RotatorResponse(session=candidate, outcome="success")
            if verdict.status == SessionStatus.LIMITED:
                self.pool.mark_limited(candidate.session_id, reason=verdict.reason)
            else:
                self.pool.mark_auth_required(candidate.session_id, reason=verdict.reason)

        # No eligible session: fail fast, explicit outcome, no submission
        all_excluded = bool(excluded) and all(s.session_id in excluded for s in pool.sessions)
        reason = "all_sessions_excluded" if all_excluded else "all_sessions_limited"
        return RotatorResponse(
            session=None,
            outcome="no_eligible_session",
            reason=reason,
            recovery_action=(
                "All sessions in the pool are rate-limited or excluded. "
                "Reduce request throughput or add authorized accounts."
            ),
        )
```

The code sample above mirrors `SessionRotator.rotate` in `modules/session/src/capabilities_session_rotator.py`, including the `empty_pool` early return and the verdict-marking branches; it omits only the metrics counters.

**CAPTCHA / access-control stop:** A CAPTCHA or any provider access-control stop halts immediately. No bypass is attempted. The affected session is marked `AUTH_REQUIRED` with reason `EXPIRED` or `NETWORK` as appropriate.

### Session Management Commands

```bash
# List all sessions
qwen-web-arwaky session list

# Add a new session (via login) — authorized accounts only
qwen-web-arwaky session login --name "personal"

# Remove a session
qwen-web-arwaky session remove session_2

# Test session health (ping test)
qwen-web-arwaky session health

# Show rotation status
qwen-web-arwaky session status
```

### Recovery Guidance

- **Reduce throughput:** Set `QWEN_WEB_MAX_WORKERS=2` and `QWEN_SWARM_CONCURRENCY=2` when limits are active.
- **Authorized accounts only:** Per the policy gate at the top of this document — add only accounts the operator owns and controls.
- **No reset-time promise:** The system does not claim a quota resets by a specific time. Use the operator's judgment.

### Workflow for Swarm

```python
# Before swarm starts:
pool = SessionPool.load()
rotator = SessionRotator(pool)

# For each role in swarm:
for role in roles:
    result = await rotator.execute_with_rotation(prompt=f"Act as {role}. {instructions}", attachment=attachment_file)
    outputs[role] = result
```

### Session Storage Layout

```
~/.local/share/qwen-web-arwaky/
├── sessions/
│   ├── session_1/
│   │   ├── Default/              # Chromium profile
│   │   │   ├── Cookies           # Session cookies
│   │   │   ├── Local State       # Profile metadata
│   │   │   └── ...
│   │   └── session.json          # Metadata
│   ├── session_2/
│   │   └── ...
│   └── session_3/
│       └── ...
└── sessions.json                 # Pool configuration
```

### Implementation Phases

#### Phase 1: Session Storage (1-2 days)
- [ ] Create session directory structure
- [ ] Implement `SessionInfo` dataclass
- [ ] Add CLI commands: `session login --name`, `session remove`, `session list`
- [ ] Store Chromium profiles per session

#### Phase 2: Health Checker (1 day)
- [ ] Implement ping test (`SessionLimitChecker`)
- [ ] Add rate limit detection logic
- [ ] Test with real Qwen responses
- [ ] Add `session health` command

#### Phase 3: Rotation Logic (1-2 days)
- [ ] Implement `SessionRotator` class
- [ ] Add round-robin fallback
- [ ] Integrate with existing orchestrators
- [ ] Update `AppConfig` with session pool

#### Phase 4: Swarm Integration (1 day)
- [ ] Update `SwarmOrchestrator` to use rotator
- [ ] Add session tracking per role
- [ ] Implement graceful degradation

#### Phase 5: CLI/TUI Integration (1 day)
- [ ] Add session status to TUI
- [ ] Show rotation info in logs
- [ ] Add `session status` command

### Files to Create/Modify

**New Files:**
- `modules/shared/src/taxonomy_session_vo.py` — Session VOs
- `modules/shared/src/contract_session_aggregate.py` — Session protocol
- `modules/core/src/capabilities_session_manager.py` — Session storage
- `modules/session/src/capabilities_session_limit_checker.py` — Ping test
- `modules/core/src/agent_session_rotator.py` — Rotation logic
- `modules/cli/src/surface_cli_sessions_command.py` — CLI handler

**Modified Files:**
- `modules/shared/src/taxonomy_core_vo.py` — Add `SessionPool` to `AppConfig`
- `modules/core/src/agent_swarm_orchestrator.py` — Use rotator
- `modules/core/src/agent_direct_prompt_orchestrator.py` — Use rotator
- `modules/core/src/agent_attachment_prompt_orchestrator.py` — Use rotator
- `modules/cli/src/surface_cli_main_entry.py` — Add sessions subcommand
- `modules/tui/src/surface_tui_app.py` — Show session status

### Testing Strategy

```python
# Test ping detection
def test_ping_detects_rate_limit():
    session = create_fake_session(limited=True)
    checker = SessionLimitChecker()
    assert checker.check_session(session) == False


def test_ping_detects_healthy():
    session = create_fake_session(limited=False)
    checker = SessionLimitChecker()
    assert checker.check_session(session) == True


# Test rotation
def test_rotation_fallback():
    pool = create_pool_with_3_sessions()
    pool.mark_limited("session_1", reason="QUOTA")
    rotator = SessionRotator(pool)
    result = rotator.execute_with_rotation("ping")
    assert result.used_session == "session_2"


# Test all limited
def test_all_sessions_limited():
    pool = create_pool_with_3_sessions()
    for s in pool.sessions:
        pool.mark_limited(s.session_id, reason="QUOTA")
    rotator = SessionRotator(pool)
    response = rotator.rotate(RotatorRequest())
    assert response.session is None
    assert response.outcome == "no_eligible_session"
    assert response.reason == "all_sessions_limited"
```

### Metrics to Track

```python
@dataclass
class RotationMetrics:
    total_attempts: int = 0
    successful_rotations: int = 0
    sessions_exhausted: int = 0
    average_rotation_time_ms: float = 0.0
```

### Error Messages

```
✅ Success: "Request sent using session_2 (session_1 is rate-limited)"
⚠️  Warning: "2 of 3 sessions available. Add more sessions for better reliability."
❌ Error: "All sessions rate-limited. Please wait until tomorrow or add more accounts."
ℹ️  Info: "Auto-rotated to healthy session after detecting limit on session_1"
```

### Security Considerations

1. **Session Storage**: Encrypt cookie files if storing sensitive data
2. **Rate Limit Detection**: Don't log full responses, only status
3. **Account Boundaries**: Each session is independent, no shared state

### Future Enhancements

1. **Smart Scheduling**: Stagger requests to avoid hitting limits
2. **Predictive Rotation**: Track usage patterns, rotate before limit
3. **Session Weighting**: Some sessions get priority based on usage
4. **Cloud Sync**: Sync session pool across devices

---

## Implementation Priority

| Priority | Feature | Est. Time |
|----------|---------|-----------|
| P0 | Session storage + CLI | 2 days |
| P1 | Health checker (ping) | 1 day |
| P2 | Rotation logic | 1.5 days |
| P3 | Swarm integration | 1 day |
| P4 | TUI integration | 0.5 days |

**Total Estimated: 6 days**

---

## Next Steps

1. ✅ Define architecture and data model
2. ⏭️ Implement Phase 1: Session storage
3. ⏳ Implement Phase 2: Health checker
4. ⏳ Implement Phase 3: Rotation logic
5. ⏳ Implement Phase 4: Swarm integration
6. ⏳ Implement Phase 5: CLI/TUI integration
