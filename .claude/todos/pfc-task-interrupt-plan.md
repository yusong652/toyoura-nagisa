# PFC Task Interrupt Mechanism Plan

## Problem Statement

When a PFC task is executed via `MainThreadExecutor`, the main thread is blocked during `itasca.command("cycle N")` or `model solve` execution. Currently, there is no way to interrupt a running task from pfc-server.

### Constraints
- PFC uses in-process IPython kernel - `Ctrl+C` (SIGINT) does not work
- `itasca.command()` transfers control to PFC C++ core
- Python thread cannot be externally interrupted during C extension execution

## Solution: Callback-based Interrupt

### Validated Findings (2024-12-16)

| Test | Result |
|------|--------|
| Ctrl+C interrupt | Not supported (in-process kernel) |
| `itasca.set_callback()` invocation | Works |
| Exception in callback stops cycle | Works |
| Exception wrapped as ValueError | Yes, properly caught |

### Test Code (Verified)
```python
import itasca

def test_interrupt():
    print("Callback called!")
    raise KeyboardInterrupt("Test interrupt")

itasca.set_callback("test_interrupt", 1.0)
itasca.command("cycle 1000")  # Successfully interrupted
```

## Implementation Plan

### Phase 1: Verify Callback in Script Context

**Status**: Pending (2024-12-17)

Test that callback works when script is executed via `exec()`:
```python
# test_callback_in_script.py
import itasca

def my_callback():
    print("Callback from script!")

itasca.set_callback("my_callback", 1.0)
itasca.command("cycle 100")
print("Cycle completed")
```

Test methods:
1. Via toyoura-nagisa pfc_execute_task
2. Via user python console: `exec(open("test_callback_in_script.py").read())`

### Phase 2: InterruptManager Implementation

Location: `pfc-server/server/interrupt_manager.py`

```python
import threading

class InterruptManager:
    """Thread-safe interrupt flag management for PFC tasks."""

    def __init__(self):
        self._flags = {}  # task_id -> bool
        self._lock = threading.Lock()

    def request_interrupt(self, task_id: str) -> None:
        """Set interrupt flag for a task (called from WebSocket handler)."""
        with self._lock:
            self._flags[task_id] = True

    def check_interrupt(self, task_id: str) -> bool:
        """Check if interrupt requested (called from callback - must be fast)."""
        return self._flags.get(task_id, False)

    def clear(self, task_id: str) -> None:
        """Clear interrupt flag after task completion."""
        with self._lock:
            self._flags.pop(task_id, None)

# Global singleton
_interrupt_manager = InterruptManager()

def get_interrupt_manager() -> InterruptManager:
    return _interrupt_manager
```

### Phase 3: Auto-inject Callback in Script Executor

Location: `pfc-server/server/script_executor.py`

Modify `_execute_script_sync()` to inject interrupt callback before script execution:

```python
def _execute_script_sync(self, script_path, script_content, output_buffer, task_id):
    # Register interrupt callback before script execution
    interrupt_manager = get_interrupt_manager()

    def _pfc_interrupt_check():
        if interrupt_manager.check_interrupt(task_id):
            raise InterruptedError(f"Task {task_id} interrupted by user")

    # Inject callback into execution context
    exec_context = {
        "itasca": self.itasca,
        "_pfc_interrupt_check": _pfc_interrupt_check
    }

    # Register callback with PFC
    self.itasca.set_callback("_pfc_interrupt_check", 1.0)

    try:
        # Execute script...
        pass
    finally:
        # Always remove callback after execution
        self.itasca.remove_callback("_pfc_interrupt_check", 1.0)
        interrupt_manager.clear(task_id)
```

### Phase 4: WebSocket API for Interrupt

Location: `pfc-server/server/server.py`

Add new message type:
```python
async def handle_message(self, websocket, message):
    msg_type = message.get("type")

    if msg_type == "interrupt_task":
        task_id = message.get("task_id")
        interrupt_manager = get_interrupt_manager()
        interrupt_manager.request_interrupt(task_id)
        return {"status": "interrupt_requested", "task_id": task_id}
```

### Phase 5: Backend Integration

Location: `packages/backend/infrastructure/pfc/websocket_client.py`

Add method:
```python
async def interrupt_task(self, task_id: str) -> Dict[str, Any]:
    """Request interrupt for a running PFC task."""
    return await self._send_message({
        "type": "interrupt_task",
        "task_id": task_id
    })
```

### Phase 6: UI Integration

- CLI: Add cancel keybinding or `/cancel` command
- Web: Add cancel button in task status display

## Architecture Flow

```
User requests cancel (CLI/Web)
           |
           v
Backend: pfc_websocket_client.interrupt_task(task_id)
           |
           v
WebSocket message: {"type": "interrupt_task", "task_id": "xxx"}
           |
           v
pfc-server: InterruptManager.request_interrupt(task_id)
           |
           v
PFC cycle calls callback: _pfc_interrupt_check()
           |
           v
Callback checks flag, raises InterruptedError
           |
           v
Cycle stops, exception caught by MainThreadExecutor
           |
           v
Future.set_exception(), task marked as interrupted
           |
           v
Status returned to user: "Task interrupted"
```

## Open Questions

1. **Callback frequency**: What does `1.0` in `set_callback(func, 1.0)` mean?
   - Per cycle? Per timestep? Need to verify.

2. **Performance impact**: Is checking a dict lookup every cycle acceptable?
   - Should be negligible, but worth measuring.

3. **Cleanup on server restart**: How to handle orphaned interrupt flags?

## Success Criteria

- [ ] Phase 1 verified: Callback works in script context
- [ ] Interrupt request successfully stops running cycle
- [ ] Task status correctly shows "interrupted"
- [ ] No impact on normal task execution performance
- [ ] Executor continues processing other tasks after interrupt
