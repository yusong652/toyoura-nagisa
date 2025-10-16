# Timeout Parameter Mismatch Analysis

## Problem Discovery

User feedback: "客户端 以及 pfc 服务器 executor的timeout必须要和我们的工具相匹配才行"

## Current Timeout Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ MCP Tool (pfc_commands.py:96)                                   │
│ timeout: int = 30000  (milliseconds)                            │
│ run_in_background: bool = False                                 │
└──────────────────┬──────────────────────────────────────────────┘
                   │ client.send_command(command, arg, params, timeout, run_in_background)
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket Client (websocket_client.py:275-284)                  │
│ Signature:                                                      │
│   send_command(                                                 │
│     command,                    # arg 1                         │
│     arg,                        # arg 2                         │
│     params,                     # arg 3                         │
│     timeout_ms: int = 30000,    # arg 4 ← MCP timeout goes here│
│     run_in_background: bool,    # arg 5                         │
│     timeout: float = 30.0,      # arg 6 ← NOT PASSED! Uses default│
│     max_retries: int = 2        # arg 7                         │
│   )                                                             │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   ├─── Send message via WebSocket (line 369)
                   │    Message includes: {"timeout_ms": timeout_ms, "run_in_background": ...}
                   │
                   └─── await asyncio.wait_for(future, timeout=timeout)  # line 373
                        ⚠️ Uses default timeout=30.0 seconds (WebSocket communication timeout)

                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ PFC Server (server.py:104-107)                                  │
│ timeout_ms = data.get("timeout_ms", 30000)  # Receives correctly│
│ result = await executor.execute_command(..., timeout_ms, ...)   │
└──────────────────┬──────────────────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│ Executor (executor.py:162-194)                                  │
│ timeout_seconds = timeout_ms / 1000.0       # Convert to seconds│
│ result = await loop.run_in_executor(                            │
│     None,                                                       │
│     future.result,                                              │
│     timeout_seconds  # Use specified timeout for command        │
│ )                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## The Mismatch Problem

### Scenario: User Requests 60-second Timeout

**User's Intent**:
```python
pfc_execute_command(
    command="model cycle",
    arg=100000,
    timeout=60000,  # 60 seconds
    run_in_background=False
)
```

**What Actually Happens**:

1. **MCP Tool → WebSocket Client** (line 96):
   ```python
   await client.send_command(command, arg, params or {}, timeout, run_in_background)
   #                                                    ^^^^^^^ = 60000 ms
   ```
   - `timeout_ms` = 60000 ✓ (correctly passed)
   - `timeout` = 30.0 ✗ (uses default, NOT passed!)

2. **WebSocket Client Behavior**:
   - Sends message to PFC server with `timeout_ms: 60000` ✓
   - Waits for response with `asyncio.wait_for(future, timeout=30.0)` ✗
   - **WebSocket times out at 30 seconds**, even though command needs 60 seconds!

3. **PFC Server/Executor**:
   - Receives `timeout_ms: 60000` correctly ✓
   - Sets command timeout to 60 seconds ✓
   - Command executes for 35 seconds
   - **Server tries to send result, but WebSocket client already disconnected at 30s!**

### Timeline Visualization

```
Time:  0s         10s        20s        30s        40s        50s        60s
       │          │          │          │          │          │          │
Client: ├──────────────────────────────X (timeout at 30s)
        │                              │
        │                              └─ TimeoutError raised
        │
Server:  ├───────────────────────────────────────────────────────────────┤
         │                                                               │
         └─ Command executing...                                        └─ Result ready (but client gone!)
```

## Impact

1. **False Timeout Errors**: Client reports timeout even when command completes successfully
2. **Orphaned Tasks**: Server completes work but can't return results
3. **User Confusion**: Setting higher timeout doesn't work as expected
4. **Resource Waste**: Commands execute to completion but results are lost

## Solution

WebSocket communication timeout must be **greater than** command execution timeout to allow result transmission.

### Recommended Fix

```python
# In pfc_commands.py:96
result = await client.send_command(
    command,
    arg,
    params or {},
    timeout_ms=timeout,                    # Command execution timeout (ms)
    run_in_background=run_in_background,
    timeout=timeout / 1000.0 + 10.0       # WebSocket timeout (seconds) + buffer
)
```

**Buffer Rationale**:
- `timeout / 1000.0`: Convert command timeout to seconds
- `+ 10.0`: Add 10-second buffer for:
  - Network latency (typically <100ms)
  - JSON serialization (large results: ~1-2s)
  - WebSocket frame overhead (~100ms)
  - Safety margin for GC pauses, system load, etc.

**Edge Cases**:
- Minimum buffer: 5 seconds (for very fast commands)
- Maximum timeout: Respect `MAX_COMMAND_TIMEOUT_MS = 600000` (10 minutes)

### Same Issue in `pfc_execute_script`

Need to check if script tool has the same problem.

## Test Verification

After fix, test should show:
1. 60-second timeout: WebSocket waits 70 seconds, command completes at ~59s → Success ✓
2. 3-second timeout: WebSocket waits 13 seconds, command times out at 3s → Timeout error captured ✓
3. Background mode: WebSocket times out quickly (task_id returned) → Success ✓

## Solution Implemented ✅

### Design Decision: N+10 (Dynamic Buffer)

**Rationale**: WebSocket timeout is infrastructure overhead, not business logic.
- LLM controls: `timeout_ms` (business: "command needs 60 seconds")
- System calculates: WebSocket timeout (infrastructure: 60s + buffer)
- User perception: Setting "60s timeout" means "60s for command execution"

### Implementation

**1. Added `_calculate_websocket_timeout()` method** (`websocket_client.py:70-122`)

```python
def _calculate_websocket_timeout(self, timeout_ms: int, run_in_background: bool) -> float:
    """Calculate WebSocket timeout based on command timeout + infrastructure buffer."""
    if run_in_background:
        return 10.0  # Quick response with task_id
    else:
        command_timeout_sec = timeout_ms / 1000.0
        # Dynamic buffer: 10s for small commands, 20% for large commands
        buffer = 10.0 if command_timeout_sec < 10 else max(10.0, command_timeout_sec * 0.2)
        return min(command_timeout_sec + buffer, 600.0)  # Max 10 minutes
```

**2. Updated `send_command()`** (`websocket_client.py:329-443`)
- Removed `timeout` parameter
- Auto-calculates WebSocket timeout
- Enhanced error message with infrastructure details

**3. Updated `send_script()`** (`websocket_client.py:465-567`)
- Removed `timeout` parameter
- Handles `timeout_ms=None` case (no script timeout)
- Same auto-calculation logic

**4. Updated MCP tools** (`pfc_commands.py:97-103`, `pfc_script.py:78-82`)
- Removed passing `timeout` parameter
- Uses keyword arguments for clarity
- Added comments explaining auto-calculation

### Benefits

1. ✅ **Separation of Concerns**: LLM controls business logic, infrastructure is automatic
2. ✅ **Simplified API**: One timeout parameter instead of two
3. ✅ **Correct Behavior**: WebSocket always waits long enough for command + result
4. ✅ **Intuitive**: "60s timeout" means "60s for command", not "WebSocket gives up at 30s"
5. ✅ **Protected**: No infinite waits, clear timeout boundaries

### Examples

| User Request | Command Timeout | WebSocket Timeout | Behavior |
|-------------|----------------|-------------------|----------|
| `timeout=3000` | 3s | 13s | 3s + 10s buffer |
| `timeout=60000` | 60s | 72s | 60s + 12s buffer (20%) |
| `timeout=600000` | 600s | 600s | Capped at 10 min max |
| `run_in_background=True` | Any | 10s | Quick task_id response |

## Current Status

- ✅ **Implemented**: Auto-calculated WebSocket timeout in `websocket_client.py`
- ✅ **Updated**: MCP tools (`pfc_commands.py`, `pfc_script.py`)
- 🧪 **Next**: Test with timeout scenarios to verify correct behavior
