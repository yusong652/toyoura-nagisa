# PFC WebSocket Server

> **Independent WebSocket service for ITASCA PFC integration**
> Runs inside PFC GUI's IPython environment, exposing PFC Python SDK as remote API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.6+](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/downloads/)

---

## What is this?

**PFC WebSocket Server** is a standalone service that enables remote control of [ITASCA PFC](https://www.itascacg.com/software/pfc) (Particle Flow Code) discrete element simulations through WebSocket communication.

### Key Characteristics

- ✅ **Independent Service**: Runs in PFC's Python environment (not part of client applications)
- ✅ **External Dependency**: Similar to PostgreSQL or Redis for client applications
- ✅ **Production-Grade**: Non-blocking task management, auto-reconnect, thread-safe execution
- ✅ **Zero Dependencies**: Only requires `websockets` library in PFC Python

### Architecture Position

```
┌─────────────────┐     WebSocket      ┌──────────────────┐     API       ┌────────────┐
│  Client Apps    │ ◄───────────────── │  PFC Server      │ ◄──────────── │ ITASCA SDK │
│  (e.g. aiNagisa)│     ws://9001      │  (This Project)  │   itasca.*    │   (PFC)    │
└─────────────────┘                    └──────────────────┘               └────────────┘
     Python 3.11+                           Python 3.6+                    Main Thread
     Any machine                            PFC GUI Process                Thread-Sensitive
```

**Not part of aiNagisa runtime** - This server is an external dependency that happens to be distributed with aiNagisa for convenience.

---

## 🚀 Quick Start

### Prerequisites

- ITASCA PFC 7.0+ with Python support
- Python 3.6+ (PFC's embedded Python)
- `websockets` library

### Installation

**Step 1: Install websockets in PFC Python**

In PFC GUI Python Console:
```python
import subprocess
subprocess.run(["pip", "install", "websockets"])
```

**Step 2: Start the server**

```python
# Adjust path to your installation
exec(open(r'C:\path\to\pfc-server\start_server.py', encoding='utf-8').read())
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

**Step 3: Connect from client**

```python
import asyncio
import websockets
import json

async def test_connection():
    async with websockets.connect("ws://localhost:9001") as ws:
        # Send command
        await ws.send(json.dumps({
            "type": "command",
            "command_id": "test-001",
            "command": "ball generate",
            "params": {"number": 100}
        }))

        # Receive result
        result = json.loads(await ws.recv())
        print(result)

asyncio.run(test_connection())
```

---

## 🏗️ Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                 PFC WebSocket Server (in PFC Process)               │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  WebSocket Server (Background Thread)                         │ │
│  │  - Accept connections, non-blocking message handling          │ │
│  └────────────┬──────────────────────────────┬──────────────────┘ │
│               │                               │                    │
│  ┌────────────▼──────────────┐  ┌────────────▼─────────────────┐ │
│  │  CommandExecutor          │  │  ScriptExecutor              │ │
│  │  - PFC command assembly   │  │  - Python script execution   │ │
│  │  - Task classification    │  │  - Output capture            │ │
│  └────────────┬──────────────┘  └────────────┬─────────────────┘ │
│               │                               │                    │
│  ┌────────────▼───────────────────────────────▼─────────────────┐ │
│  │  MainThreadExecutor (Queue-based)                            │ │
│  │  - Thread-safe queue → IPython main thread                  │ │
│  │  - Ensures PFC SDK callbacks work correctly                 │ │
│  └────────────┬──────────────────────────────────────────────────┘ │
│               │                                                     │
│  ┌────────────▼──────────────────────────────────────────────────┐ │
│  │  ITASCA PFC SDK (itasca module) - MAIN THREAD ONLY           │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  TaskManager (Independent)                                    │ │
│  │  - Track long-running task lifecycle                         │ │
│  │  - Non-blocking status queries (not PFC commands)            │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Hybrid Threading**: WebSocket server runs in background thread, PFC commands execute in main thread
2. **Task Classification**: Auto-detect short vs long-running operations
3. **Non-blocking**: Long tasks return task_id immediately, query progress separately
4. **Thread Safety**: All PFC SDK calls go through main thread queue

---

## 📖 API Reference

### Message Types

#### 1. Execute Command

```json
{
  "type": "command",
  "command_id": "unique-id",
  "command": "ball generate",
  "arg": null,
  "params": {"number": 100, "radius": 0.5},
  "timeout_ms": 30000,
  "run_in_background": false
}
```

**Response (Short Task)**:
```json
{
  "type": "result",
  "command_id": "unique-id",
  "status": "success",
  "message": "PFC command executed: ball generate number 100 radius 0.5",
  "data": null
}
```

**Response (Long Task)**:
```json
{
  "type": "result",
  "command_id": "unique-id",
  "status": "pending",
  "message": "Task submitted. Use check_task_status to query progress.",
  "data": {
    "task_id": "3614a7dd-...",
    "command": "model cycle 80000"
  }
}
```

#### 2. Execute Script

```json
{
  "type": "script",
  "command_id": "unique-id",
  "script_path": "/absolute/path/to/script.py",
  "timeout_ms": null,
  "run_in_background": true
}
```

#### 3. Check Task Status

```json
{
  "type": "check_task_status",
  "command_id": "unique-id",
  "task_id": "3614a7dd-..."
}
```

**Response**:
```json
{
  "type": "result",
  "status": "running",
  "message": "Task executing (elapsed 15.23s)",
  "data": {
    "elapsed_time": 15.23,
    "output": "Cycle 10000: unbalanced=1.2e-5\n..."
  }
}
```

#### 4. List Tasks

```json
{
  "type": "list_tasks",
  "command_id": "unique-id"
}
```

---

## 🔧 Configuration

Create `config.py` from `config_example.py`:

```python
# WebSocket Server Configuration
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 9001

# Ping Configuration (for long-running tasks)
PING_INTERVAL = 120  # seconds
PING_TIMEOUT = 300   # seconds
```

---

## 📁 Project Structure

```
pfc-server/
├── server/                        # Server implementation
│   ├── server.py                  # WebSocket server + routing
│   ├── executor.py                # Command executor + task classification
│   ├── script_executor.py         # Python script execution
│   ├── main_thread_executor.py    # Queue-based main thread execution
│   └── task_manager.py            # Long-running task tracking
├── examples/                      # Example PFC projects
│   ├── scripts/                   # Example scripts
│   │   └── gravity_settling_damped.py
│   └── test_scripts/              # Test scripts
│       └── complete_simulation.py
├── start_server.py                # Startup script
├── config_example.py              # Configuration template
├── pyproject.toml                 # Dependencies
└── README.md                      # This file
```

---

## 🐛 Troubleshooting

### Server won't start

```python
# Install websockets in PFC Python
>>> import subprocess
>>> subprocess.run(["pip", "install", "websockets"])
```

### Tasks not processing (IPython Hook Mode)

```python
# Run any command to trigger queue processing
>>> pass  # or 1+1

# Check queue size
>>> get_queue_size()

# Switch to continuous mode (blocks shell)
>>> run_task_loop()
```

### Long task timeout

Add command to `LONG_RUNNING_COMMANDS` in `server/executor.py`:

```python
LONG_RUNNING_COMMANDS = {
    "model solve",
    "model cycle",
    "your_custom_command",  # Add here
}
```

### Connection failed

- Check server is running: `server_status()`
- Check port 9001 is free
- Check firewall allows localhost:9001

---

## 🧪 Testing

If using with aiNagisa, run the integration demo:

```bash
# From aiNagisa root (with PFC server running)
uv run python examples/pfc_integration/DEMo.py
```

Tests: normal tasks, long tasks, status queries, WebSocket responsiveness, main thread execution.

---

## 💡 Best Practices

### DO

- ✅ Use segmented scripts for long simulations (PFC standard practice)
- ✅ Query task status instead of blocking
- ✅ Pass native Python types (auto-converted to PFC format)
- ✅ Run any IPython command to trigger task processing (hook mode)

### DON'T

- ❌ Submit large cycle counts as direct commands (use scripts instead)
- ❌ Wait indefinitely for long tasks (use task_id + check_status)
- ❌ Forget to process queue in hook mode

---

## 📚 Additional Resources

- **[ITASCA PFC Documentation](https://www.itascacg.com/software/pfc)**: Official PFC docs
- **Integration Example**: See `examples/` directory for PFC project templates
- **Client Implementation**: If using aiNagisa, see `backend/infrastructure/pfc/` for WebSocket client

---

## 📄 License

Same as parent aiNagisa project - see LICENSE file in repository root.

---

## 🙏 Acknowledgments

**Architecture & Design**: Nagisa Toyoura
**Implementation**: Claude (Anthropic)
**ITASCA SDK**: ITASCA Consulting Group, Inc.

---

**This is an independent service, not a module of aiNagisa.**
It runs in PFC GUI's Python environment and can be used by any WebSocket client.