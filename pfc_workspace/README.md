# PFC Server - ITASCA PFC WebSocket Communication Bridge

> **Real-time bidirectional communication between aiNagisa and ITASCA PFC software**

This UV workspace member provides a lightweight WebSocket server that enables aiNagisa to control ITASCA PFC simulations remotely. The server runs directly in PFC's Python environment (GUI IPython shell or command-line console) and exposes the ITASCA SDK through a WebSocket API.

## 🎯 Key Features

- ✅ **Zero External Dependencies**: Runs inside PFC's Python environment with direct `itasca` module access
- ✅ **Dual Startup Modes**: Launch from GUI IPython shell OR command-line console
- ✅ **Real-time Communication**: WebSocket for low-latency bidirectional communication
- ✅ **Background Execution**: Non-blocking server mode allows continued PFC use
- ✅ **Type-Safe Protocol**: Structured JSON messages with clear error handling
- ✅ **MCP Integration**: Seamless integration with aiNagisa's Model Context Protocol

## 📁 Project Structure

```
pfc_workspace/
├── pfc_server/              # WebSocket server package
│   ├── __init__.py
│   └── server.py            # Main server implementation
├── start_server.py          # Startup script for PFC Python console
├── requirements.txt         # PFC Python environment dependencies
├── pyproject.toml           # UV workspace configuration
├── README.md                # This file
└── QUICKSTART.md            # Quick start guide
```

## 📋 Prerequisites

### PFC Python Environment Setup

The server requires `websockets` package in PFC's Python environment.

**Install dependencies in PFC Python:**

```bash
# Using PFC's pip (replace path with your PFC installation)
"C:\Program Files\Itasca\PFC700\exe64\python36\Scripts\pip.exe" install -r "C:\Dev\Han\aiNagisa\pfc_workspace\requirements.txt"
```

**Verify installation:**

```bash
"C:\Program Files\Itasca\PFC700\exe64\python36\Scripts\pip.exe" list | findstr websockets
```

Expected: `websockets (9.x or higher)`

## 🚀 Quick Start

### 1. Start PFC Server

**In PFC GUI Python Shell or Console**:

```python
# Add workspace to Python path and run startup script
import sys
sys.path.append(r'<AINAGISA_ROOT>\pfc_workspace')
exec(open(r'<AINAGISA_ROOT>\pfc_workspace\start_server.py', encoding='utf-8').read())
```

**Example** (replace with your actual path):
```python
import sys
sys.path.append(r'D:\Projects\aiNagisa\pfc_workspace')
exec(open(r'D:\Projects\aiNagisa\pfc_workspace\start_server.py', encoding='utf-8').read())
```

### 2. Use in aiNagisa

Start backend and select **PFC Expert** profile in frontend:

```
User: Create a ball with radius 0.5 and run 1000 cycles
AI: [Uses pfc_execute_command tool automatically]
```

## 🏗️ Architecture

```
┌─────────────────────┐    WebSocket     ┌──────────────────────┐    Python API    ┌──────────────────┐
│  aiNagisa Backend   │◄────────────────►│   PFC Server         │◄────────────────►│  ITASCA PFC SDK  │
│  (MCP Tool)         │  ws://localhost  │   (in PFC process)   │   Direct import  │  (itasca module) │
│  pfc_execute_cmd    │     :9001        │   • Command executor │                  │  • ball.create   │
│                     │                  │   • Message handler  │                  │  • cycle         │
│                     │                  │   • Error handling   │                  │  • ball.list     │
└─────────────────────┘                  └──────────────────────┘                  └──────────────────┘
```

**Key Design Decisions**:

1. **Single-file server**: All server logic in `server.py` (~300 lines) for easy deployment
2. **In-process execution**: Server runs in PFC's Python process for direct SDK access
3. **Async WebSocket**: Using `websockets` library for efficient I/O
4. **Command-based protocol**: Simple JSON messages for flexibility

## 📚 MCP Tool

The server exposes a single unified MCP tool through aiNagisa:

**`pfc_execute_command`** - Execute any ITASCA PFC SDK command

Supports two command patterns:
- **String commands**: `command="command"`, `params='{"cmd": "ball create radius 0.5"}'`
- **Direct API calls**: `command="ball.count"`, `params='{}' (optional)`

Example usage in chat:
```
User: Create a ball with radius 0.5
AI: [Uses pfc_execute_command with command="command", params='{"cmd": "ball create radius 0.5"}']

User: How many balls are there?
AI: [Uses pfc_execute_command with command="ball.count"]
```

## 🔧 Technical Details

### Communication Protocol

**Command Message** (aiNagisa → PFC):
```json
{
  "type": "command",
  "command_id": "uuid-v4",
  "command": "ball.create",
  "params": {
    "radius": 0.5,
    "position": [0, 0, 0]
  }
}
```

**Result Message** (PFC → aiNagisa):
```json
{
  "type": "result",
  "command_id": "uuid-v4",
  "status": "success",
  "data": {"ball_id": 12345},
  "message": "Ball created successfully"
}
```

**Event Message** (PFC → aiNagisa, async):
```json
{
  "type": "event",
  "event_type": "simulation_progress",
  "data": {"step": 1000, "total": 10000}
}
```

### Error Handling

All errors return standardized responses:

```json
{
  "type": "result",
  "status": "error",
  "message": "Command execution failed",
  "error": "Detailed error message"
}
```

### Server Implementation Highlights

- **Async I/O**: `asyncio` and `websockets` for efficient concurrency
- **Command Executor**: Parses dot-notation commands to SDK calls
- **Result Serialization**: Converts PFC objects to JSON-safe types
- **Connection Management**: Handles multiple simultaneous clients
- **Graceful Shutdown**: Clean disconnect on Ctrl+C or PFC exit

## 🧪 Testing

### Manual Test (without aiNagisa)

```python
# In PFC Python environment
>>> from pfc_server import server
>>> server.start()  # Start in foreground for testing
```

Then in another Python console:

```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:9001"
    async with websockets.connect(uri) as ws:
        # Send command
        await ws.send(json.dumps({
            "type": "command",
            "command_id": "test-123",
            "command": "ball.create",
            "params": {"radius": 0.5}
        }))

        # Receive result
        result = await ws.recv()
        print(json.loads(result))

asyncio.run(test())
```

### Integration Test (with aiNagisa)

See [QUICKSTART.md](QUICKSTART.md) for full workflow testing.

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)**: Step-by-step setup and usage guide
- **Backend Code**: `backend/infrastructure/mcp/tools/pfc/` - MCP integration

## 🐛 Troubleshooting

### Server won't start
- **Check**: Is `websockets` installed in PFC Python? (See Prerequisites section)
- **Check**: Port 9001 available? (no conflicts)
- **Check**: Using PFC's Python, not system Python

### Connection failed
- **Check**: Server running in PFC console? (look for "Server running" message)
- **Check**: Firewall blocking localhost:9001?

### Commands not executing
- **Check**: Server logs in PFC console for error details
- **Check**: Command syntax matches ITASCA SDK documentation

See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions.

## 📄 License

Same as parent aiNagisa project.

## 🔗 Links

- [aiNagisa Repository](https://github.com/yusong652/aiNagisa)
- [ITASCA PFC Documentation](https://www.itascacg.com/software/pfc)
- [UV Workspace Documentation](https://docs.astral.sh/uv/concepts/workspaces/)

---

**Built with ❤️ for seamless PFC-AI integration**
