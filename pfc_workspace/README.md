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
├── pfc_server/
│   ├── __init__.py          # Package initialization
│   └── server.py            # Lightweight WebSocket server (single file!)
├── pyproject.toml           # UV workspace member configuration
├── README.md                # This file
├── QUICKSTART.md            # Quick start guide
└── TOOL_REFERENCE.md        # Detailed tool documentation
```

## 🚀 Quick Start

### 1. Install Dependencies

From aiNagisa root:

```bash
uv sync  # Installs all workspace members including pfc-server
```

### 2. Start PFC Server

**Option A - GUI IPython Shell** (Interactive):

```python
# In PFC GUI → Python Shell
>>> import sys
>>> sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')
>>> from pfc_server import server
>>> server.start_background()
```

**Option B - Command-Line Console** (Headless):

```
$ pfc.exe
PFC> python
>>> import sys
>>> sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')
>>> from pfc_server import server
>>> server.start_background()
```

### 3. Use in aiNagisa

Start backend and select **PFC Expert** profile in frontend:

```
User: Create a ball with radius 0.5 and run 1000 cycles
AI: [Uses pfc_create_ball and pfc_run_cycles tools automatically]
```

## 🏗️ Architecture

```
┌─────────────────────┐    WebSocket     ┌──────────────────────┐    Python API    ┌──────────────────┐
│  aiNagisa Backend   │◄────────────────►│   PFC Server         │◄────────────────►│  ITASCA PFC SDK  │
│  (MCP Tools)        │  ws://localhost  │   (in PFC process)   │   Direct import  │  (itasca module) │
│  • pfc_create_ball  │     :9001        │   • Command executor │                  │  • ball.create   │
│  • pfc_run_cycles   │                  │   • Message handler  │                  │  • cycle         │
│  • pfc_query_balls  │                  │   • Error handling   │                  │  • ball.list     │
└─────────────────────┘                  └──────────────────────┘                  └──────────────────┘
```

**Key Design Decisions**:

1. **Single-file server**: All server logic in `server.py` (~300 lines) for easy deployment
2. **In-process execution**: Server runs in PFC's Python process for direct SDK access
3. **Async WebSocket**: Using `websockets` library for efficient I/O
4. **Command-based protocol**: Simple JSON messages for flexibility

## 📚 Available Tools

The server exposes 6 MCP tools through aiNagisa:

| Tool | Purpose | Example |
|------|---------|---------|
| `pfc_execute_command` | Execute raw SDK commands | `command="ball.create", params={...}` |
| `pfc_create_ball` | Create ball particles | `radius=0.5, x=0, y=0, z=0` |
| `pfc_run_cycles` | Run simulation steps | `steps=1000` |
| `pfc_query_balls` | Query ball information | `filter_expr="radius > 0.5"` |
| `pfc_save_state` | Save model state | `filename="model.sav"` |
| `pfc_load_state` | Load model state | `filename="model.sav"` |

See [TOOL_REFERENCE.md](TOOL_REFERENCE.md) for detailed documentation.

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
- **[TOOL_REFERENCE.md](TOOL_REFERENCE.md)**: Detailed tool documentation with examples
- **[../backend/infrastructure/mcp/tools/pfc/](../backend/infrastructure/mcp/tools/pfc/)**: aiNagisa backend integration code

## 🤝 Contributing

Contributions welcome! To add new PFC tools:

1. Add tool function in `backend/infrastructure/mcp/tools/pfc/pfc_commands.py`
2. Register tool in `register_pfc_tools()` function
3. Update `backend/infrastructure/mcp/tool_profile_manager.py` PFC_TOOLS list
4. Add documentation to [TOOL_REFERENCE.md](TOOL_REFERENCE.md)

## 🐛 Troubleshooting

### Server won't start
- **Check**: Is `websockets` installed? (`pip install websockets` in PFC Python)
- **Check**: Port 9001 available? (no conflicts)

### Connection failed
- **Check**: Server running in PFC console? (look for "Server running" message)
- **Check**: Firewall blocking localhost:9001?

### Commands not executing
- **Check**: Server logs in PFC console for error details
- **Check**: Command syntax matches ITASCA SDK documentation

See [QUICKSTART.md](QUICKSTART.md) for more troubleshooting tips.

## 📄 License

Same as parent aiNagisa project.

## 🔗 Links

- [aiNagisa Repository](https://github.com/yusong652/aiNagisa)
- [ITASCA PFC Documentation](https://www.itascacg.com/software/pfc)
- [UV Workspace Documentation](https://docs.astral.sh/uv/concepts/workspaces/)

---

**Built with ❤️ for seamless PFC-AI integration**
