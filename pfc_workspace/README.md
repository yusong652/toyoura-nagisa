# PFC Server - Advanced WebSocket Integration for ITASCA PFC

> **Production-grade real-time communication between aiNagisa and ITASCA PFC with non-blocking task management**

WebSocket server enabling remote PFC control through aiNagisa. Features hybrid execution architecture, automatic task classification, and PFC best practice integration for progress monitoring.

## 🎯 Key Features

- ✅ **Hybrid Execution Architecture**: Background server + main thread command execution
- ✅ **Smart Task Classification**: Auto-detect short vs long-running operations
- ✅ **Non-blocking Execution**: Long tasks return task_id immediately, query progress later
- ✅ **Main Thread Safety**: All commands execute in IPython main thread (callback-safe)
- ✅ **Script Support**: Run Python scripts with progress monitoring (PFC standard practice)
- ✅ **Type-Driven API**: Native Python types → PFC command strings
- ✅ **Zero Dependencies**: Runs in PFC's Python environment with direct `itasca` access

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          aiNagisa Backend                               │
│  ┌─────────────────┐        ┌──────────────────┐                      │
│  │  MCP Tools      │        │  WebSocket       │                      │
│  │  - pfc_command  │───────►│  Client          │                      │
│  │  - pfc_script   │        │  - Auto-reconnect│                      │
│  │  - check_status │        │  - Retry logic   │                      │
│  └─────────────────┘        └──────────────────┘                      │
└──────────────────────────────────│──────────────────────────────────────┘
                                   │ WebSocket (ws://localhost:9001)
┌──────────────────────────────────▼──────────────────────────────────────┐
│                     PFC WebSocket Server (in PFC process)               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Background Thread (WebSocket Server)                           │   │
│  │  - Accept connections, handle messages (non-blocking)           │   │
│  └────────────┬────────────────────────────────┬───────────────────┘   │
│               │                                │                        │
│  ┌────────────▼──────────────┐   ┌────────────▼───────────────┐       │
│  │  Executor                 │   │  ScriptExecutor            │       │
│  │  - Task classification    │   │  - File execution          │       │
│  │  - Type-driven assembly   │   │  - Output capture          │       │
│  └────────────┬──────────────┘   └────────────┬───────────────┘       │
│               │                                │                        │
│  ┌────────────▼────────────────────────────────▼───────────────┐       │
│  │  MainThreadExecutor (Queue + IPython Hook)                  │       │
│  │  - Thread-safe queue → Future objects                       │       │
│  │  - Executes in IPython main thread                         │       │
│  └────────────┬────────────────────────────────────────────────┘       │
│               │                                                         │
│  ┌────────────▼─────────────────────────────────────────────────┐      │
│  │  ITASCA PFC SDK (itasca module) - MAIN THREAD ONLY          │      │
│  │  - Thread-sensitive callbacks (contact models, etc.)         │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │  TaskManager (Independent tracking)                         │       │
│  │  - Non-blocking status queries (NOT PFC commands)           │       │
│  │  - Long-running task lifecycle management                   │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

**Task Classification:**
- **Short tasks** → Execute & wait → Return result immediately
  - Examples: `model domain`, `ball generate`, `contact cmat`
- **Long tasks** → Submit & return task_id → Query status later
  - Examples: `model cycle 80000`, custom scripts

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# In PFC Python environment (one time setup)
pip install websockets

# In aiNagisa environment
cd aiNagisa
uv sync
```

### 2. Start PFC Server

In PFC GUI IPython shell or console Python mode:

```python
import sys
sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')  # Your path
exec(open(r'C:\Dev\Han\aiNagisa\pfc_workspace\start_server.py', encoding='utf-8').read())
```

You'll see:
```
======================================================================
PFC WebSocket Server Status
======================================================================
Server:
  • URL: ws://localhost:9001
  • Running: True

Task Processing Mode: hook (auto-process on any IPython command)

Commands: server_status(), get_queue_size(), run_task_loop()
======================================================================
```

### 3. Test Integration

```bash
# Run comprehensive demo (with PFC server running)
uv run python DEMo.py
```

Validates: normal tasks, long tasks, status queries, WebSocket responsiveness, main thread execution.

### 4. Use in aiNagisa

Start backend, select "PFC Expert" profile, chat!

```
User: Create 500 balls with radius 0.5, then run 80000 cycles
AI: [Creates balls → immediate result]
    [Submits long task → task_id returned]
    ⏳ Task submitted: 3614a7dd...
    Use check_task_status to query progress
```

## 📖 Usage Examples

### Normal Tasks (Immediate Results)

```python
# Via MCP tool or direct WebSocket
command = "ball generate"
params = {"number": 500, "radius": 0.5, "box": "-7 7"}

# Returns immediately:
{
  "status": "success",
  "message": "PFC command executed: ball generate number 500 radius 0.5 box -7 7",
  "data": null
}
```

### Long Tasks (Non-blocking)

```python
# Submit long task
command = "model solve"
params = {"cycle": 80000}

# Returns immediately with task_id:
{
  "status": "pending",
  "message": "Task submitted. Use check_task_status to query progress.",
  "data": {
    "task_id": "3614a7dd",
    "command": "model cycle 80000"
  }
}

# Query status (non-blocking)
check_task_status(task_id="3614a7dd")
# → "running" (elapsed 15s)
# → "success" (elapsed 59s, completed)
```

### Script Execution (PFC Best Practice)

For long tasks with progress, use segmented scripts:

```python
# progress_simulation.py
import itasca

total_cycles = 100000
checkpoint = 10000

for i in range(0, total_cycles, checkpoint):
    itasca.command(f"model cycle {checkpoint}")
    completed = i + checkpoint
    print(f"Progress: {completed}/{total_cycles} ({completed/total_cycles*100:.1f}%)")
    print(f"Unbalanced force: {itasca.mech.unbalanced_force()}")

print("Simulation completed!")
```

Submit via `send_script()` → returns task_id → query to see accumulated output.

**Why scripts?** PFC commands can't be stopped mid-execution. Segmented scripts enable:
- Progress monitoring at checkpoints
- State inspection (convergence, forces)
- Early termination decisions
- **This is PFC users' standard practice**

## 🔧 Technical Details

### Type-Driven Command Assembly

Python types → PFC format automatically:

```python
arg=True               → "true"
arg=9.81               → "9.81"
arg=(0, 0, -9.81)      → "(0,0,-9.81)"
arg="linear"           → '"linear"'
params={"property": None}  → "property"  # Boolean flag
```

### Communication Protocol

**Command → Result:**
```json
// Request
{"type": "command", "command": "model gravity", "arg": [0, 0, -9.81], "params": {}}

// Short task result (immediate)
{"status": "success", "message": "PFC command executed: model gravity (0,0,-9.81)"}

// Long task result (immediate)
{"status": "pending", "data": {"task_id": "uuid", "command": "model cycle 80000"}}
```

**Status Query → Response:**
```json
// Request
{"type": "check_task_status", "task_id": "uuid"}

// Running
{"status": "running", "message": "Task executing (15.23s)", "data": {"elapsed_time": 15.23}}

// Completed
{"status": "success", "message": "Task completed (59.17s)"}
```

### Architecture Highlights

1. **Separation of Concerns**
   - Executor: Execute commands only
   - TaskManager: Track lifecycle only
   - Server: Coordinate routing
   - Status queries bypass Executor (not PFC commands!)

2. **Non-blocking Design**
   - Long tasks return immediately
   - Client stays responsive
   - No thread pool exhaustion

3. **Main Thread Safety**
   - All PFC commands → IPython main thread queue
   - Thread-sensitive callbacks work correctly
   - Processing triggered by IPython hook

## 🐛 Troubleshooting

**Server won't start**
```python
# Install websockets in PFC Python
>>> import subprocess
>>> subprocess.run(["pip", "install", "websockets"])
```

**Tasks not processing**
```python
# IPython Hook Mode: Run any command to trigger
>>> pass  # or 1+1

# Check queue
>>> get_queue_size()

# Continuous mode (blocks shell)
>>> run_task_loop()
```

**Long task timeout**
- Task should return task_id immediately
- Add command to `LONG_RUNNING_COMMANDS` in `executor.py`:
  ```python
  LONG_RUNNING_COMMANDS = {
      "model solve",
      "model cycle",
      "your_custom_long_command",  # Add here
  }
  ```

**Connection failed**
- Server running? Check `server_status()`
- Port 9001 free? Check for conflicts
- Firewall? Allow localhost:9001

## 📁 Project Structure

```
pfc_workspace/
├── pfc_server/
│   ├── server.py                 # WebSocket server + routing
│   ├── executor.py               # Command executor + task classification
│   ├── script_executor.py        # Python script execution
│   ├── main_thread_executor.py   # Queue-based main thread execution
│   └── task_manager.py           # Long-running task tracking
├── start_server.py               # Startup script (hybrid architecture)
├── config_example.py             # Configuration template
└── README.md                     # This file
```

## 🎓 Best Practices

**DO:**
- ✅ Use segmented scripts for long simulations (PFC standard practice)
- ✅ Query task status instead of waiting for long tasks
- ✅ Pass native Python types (auto-converted to PFC format)
- ✅ Run any IPython command (`pass`) to trigger task processing

**DON'T:**
- ❌ Submit large cycle counts as direct commands (use scripts)
- ❌ Wait indefinitely for long tasks (use task_id + check_status)
- ❌ Forget to trigger task processing in hook mode

## 🧪 Testing

```bash
# Comprehensive integration test
uv run python DEMo.py

# Tests: normal tasks, long tasks, status queries, WebSocket
#        responsiveness, task completion, main thread execution
```

## 📚 Additional Resources

- **[DEMo.py](../DEMo.py)**: Complete integration example
- **Backend Code**: `backend/infrastructure/pfc/` - WebSocket client & MCP tools
- **[ITASCA PFC Docs](https://www.itascacg.com/software/pfc)**: Official PFC documentation

## 🔗 Configuration

Optional: Create `config.py` from `config_example.py` to customize:
- `WEBSOCKET_HOST`, `WEBSOCKET_PORT`
- `PING_INTERVAL`, `PING_TIMEOUT` (for long tasks)
- `AUTO_START_TASK_LOOP` (False = IPython hook mode)

## 💡 Key Insights

**Why this architecture?**
- PFC SDK callbacks are thread-sensitive → must use main thread
- Long tasks block → need non-blocking submission
- Progress monitoring required → scripts with checkpoints (PFC standard practice)
- Can't stop PFC commands → segmented execution essential

**Production-grade features:**
- Task classification prevents timeouts
- Non-blocking design maintains client responsiveness
- Separation of concerns enables clean status queries
- Type-driven API reduces string formatting errors
- Main thread safety ensures callback compatibility

## 📄 License & Support

- License: Same as parent aiNagisa project
- Issues: https://github.com/yusong652/aiNagisa/issues
- Repo: https://github.com/yusong652/aiNagisa

---

**Built with ❤️ by Nagisa Toyoura (architecture) and Claude (implementation)**
