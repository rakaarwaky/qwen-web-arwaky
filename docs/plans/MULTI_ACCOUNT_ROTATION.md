# Multi-Account Rate Limit Rotation System

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
3. **Auto-Rotation**: Transparent switching between sessions on limit detection
4. **Fallback Chain**: Try Session 1 → Session 2 → Session 3 until success

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
│  ~/.qwen-web/sessions/                                      │
│  ├── session_1/  ( Chromium profile )                       │
│  ├── session_2/  ( Chromium profile )                       │
│  └── session_3/  ( Chromium profile )                       │
└─────────────────────────────────────────────────────────────┘
```

### Data Model

```python
@dataclass
class SessionInfo:
    session_id: str           # "session_1", "session_2", etc.
    path: Path                # ~/.qwen-web/sessions/session_1/
    status: SessionStatus     # active, limited, unknown
    last_used: datetime | None
    total_requests: int = 0
    failed_requests: int = 0

class SessionStatus(str, Enum):
    ACTIVE = "active"       # Healthy, can send requests
    LIMITED = "limited"     # Hit rate limit
    UNKNOWN = "unknown"     # Not tested yet

@dataclass
class SessionPool:
    sessions: list[SessionInfo]
    current_index: int = 0
    
    def get_next_session(self) -> SessionInfo:
        """Round-robin with fallback to healthy sessions."""
        ...
    
    def mark_limited(self, session_id: str) -> None:
        """Mark session as rate-limited."""
        ...
    
    def mark_healthy(self, session_id: str) -> None:
        """Mark session as healthy after successful request."""
        ...
```

### Session Management Commands

```bash
# List all sessions
qwen-web-arwaky sessions list

# Add a new session (via login)
qwen-web-arwaky sessions add --name "personal"

# Remove a session
qwen-web-arwaky sessions remove session_2

# Test session health (ping test)
qwen-web-arwaky sessions health-check

# Show rotation status
qwen-web-arwaky sessions status
```

### Ping Test Implementation

```python
class SessionHealthChecker:
    """Quick health check using minimal ping message."""
    
    PING_MESSAGE = "Reply with just: pong"
    EXPECTED_RESPONSE = "pong"
    TIMEOUT_SECONDS = 5
    
    async def check_session(self, session: SessionInfo) -> bool:
        """Returns True if session is healthy, False if limited."""
        try:
            result = await self._send_ping(session)
            return self._is_healthy(result)
        except Exception:
            return False
    
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
    """Transparent session rotation for API calls."""
    
    def __init__(self, session_pool: SessionPool):
        self.pool = session_pool
        self.failed_sessions: set[str] = set()
    
    async def execute_with_rotation(
        self, 
        prompt: str, 
        attachment: Path | None = None
    ) -> ExecutionResult:
        """Try sessions in order until success or all exhausted."""
        sessions_to_try = self.pool.get_ordered_sessions()
        
        for session in sessions_to_try:
            # First, run health check
            if not await self.health_checker.check_session(session):
                self.pool.mark_limited(session.session_id)
                self.failed_sessions.add(session.session_id)
                continue
            
            # Session is healthy, try the actual request
            try:
                result = await self._execute(prompt, attachment, session)
                self.pool.mark_healthy(session.session_id)
                self.failed_sessions.discard(session.session_id)
                return result
            except Exception as e:
                if "rate limit" in str(e).lower():
                    self.pool.mark_limited(session.session_id)
                    self.failed_sessions.add(session.session_id)
                    continue
                raise
        
        # All sessions exhausted
        raise AllSessionsLimitedError(
            f"All {len(sessions_to_try)} sessions are rate-limited. "
            f"Wait until tomorrow or add more sessions."
        )
```

### Workflow for Swarm

```python
# Before swarm starts:
pool = SessionPool.load()
rotator = SessionRotator(pool)

# For each role in swarm:
for role in roles:
    result = await rotator.execute_with_rotation(
        prompt=f"Act as {role}. {instructions}",
        attachment=attachment_file
    )
    outputs[role] = result
```

### Session Storage Layout

```
~/.qwen-web/
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
- [ ] Add CLI commands: `sessions add`, `sessions remove`, `sessions list`
- [ ] Store Chromium profiles per session

#### Phase 2: Health Checker (1 day)
- [ ] Implement ping test (`SessionHealthChecker`)
- [ ] Add rate limit detection logic
- [ ] Test with real Qwen responses
- [ ] Add `sessions health-check` command

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
- [ ] Add `sessions status` command

### Files to Create/Modify

**New Files:**
- `modules/shared/src/taxonomy_session_vo.py` — Session VOs
- `modules/shared/src/contract_session_aggregate.py` — Session protocol
- `modules/core/src/capabilities_session_manager.py` — Session storage
- `modules/core/src/capabilities_session_health_checker.py` — Ping test
- `modules/core/src/agent_session_rotator.py` — Rotation logic
- `modules/cli/src/surface_cli_sessions_command.py` — CLI handler

**Modified Files:**
- `modules/shared/src/taxonomy_core_vo.py` — Add `SessionPool` to `AppConfig`
- `modules/core/src/agent_swarm_orchestrator.py` — Use rotator
- `modules/core/src/agent_direct_prompt_orchestrator.py` — Use rotator
- `modules/core/src/agent_attachment_prompt_orchestrator.py` — Use rotator
- `modules/cli/src/surface_cli_main_entry.py` — Add sessions subcommand
- `modules/cli/src/surface_cli_tui_app.py` — Show session status

### Testing Strategy

```python
# Test ping detection
def test_ping_detects_rate_limit():
    session = create_fake_session(limited=True)
    checker = SessionHealthChecker()
    assert checker.check_session(session) == False

def test_ping_detects_healthy():
    session = create_fake_session(limited=False)
    checker = SessionHealthChecker()
    assert checker.check_session(session) == True

# Test rotation
def test_rotation_fallback():
    pool = create_pool_with_3_sessions()
    pool.mark_limited("session_1")
    rotator = SessionRotator(pool)
    result = rotator.execute_with_rotation("ping")
    assert result.used_session == "session_2"

# Test all limited
def test_all_sessions_limited():
    pool = create_pool_with_3_sessions()
    for s in pool.sessions:
        pool.mark_limited(s.session_id)
    rotator = SessionRotator(pool)
    with pytest.raises(AllSessionsLimitedError):
        rotator.execute_with_rotation("ping")
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
