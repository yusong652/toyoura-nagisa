# PFC Integration Quick Start Guide

This guide shows you how to set up and use the PFC integration for aiNagisa.

## Architecture Overview

```
┌──────────────────┐              ┌──────────────────┐              ┌──────────────────┐
│  aiNagisa        │   WebSocket  │  PFC Server      │   Python API │  ITASCA PFC      │
│  Backend         │◄────────────►│  (IPython shell) │◄────────────►│  Software        │
│  (MCP Tools)     │  ws://9001   │  in PFC GUI      │              │  (SDK: itasca)   │
└──────────────────┘              └──────────────────┘              └──────────────────┘
```

## Setup Steps

### Step 1: Install Dependencies

From the aiNagisa root directory:

```bash
# Install all dependencies including PFC workspace
uv sync
```

### Step 2: Start PFC and Enter Python Environment

You have **two options** for starting the PFC server:

#### Option A: GUI IPython Shell (Recommended for Interactive Work)

1. Open ITASCA PFC GUI software
2. Open the IPython shell (usually via `View → Python Shell` or similar menu)
3. The IPython shell provides better debugging and interactive features

#### Option B: Command-Line Console (Recommended for Automation)

1. Open PFC command-line console (e.g., `pfc.exe` in command prompt)
2. Enter Python mode by typing `python` at the PFC prompt
3. More lightweight, suitable for server-only operation

```
PFC> python
Python mode enabled
>>>
```

### Step 3: Install websockets in PFC Python Environment

In either the PFC IPython shell or command-line Python mode:

```python
>>> import subprocess
>>> subprocess.run(["pip", "install", "websockets"])
```

**Note**: Only needed once. If PFC uses a separate Python environment, install there.

### Step 4: Start PFC WebSocket Server

**Same commands work for both GUI and command-line modes:**

```python
>>> import sys
>>> sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')  # Adjust path as needed
>>> from pfc_server import server
>>> server.start_background()  # Non-blocking mode
```

You should see:

```
✓ ITASCA SDK loaded successfully
🚀 Starting PFC WebSocket Server on localhost:9001
✓ Server running on ws://localhost:9001
✓ Server started in background
```

**Startup Mode Options**:
- `server.start_background()`: Non-blocking, allows continued use of PFC console
- `server.start()`: Blocking mode, dedicates console to server (use Ctrl+C to stop)

**Command-Line Console Advantage**: Can run PFC headless without GUI overhead, perfect for server deployments!

### Step 5: Start aiNagisa Backend

In a separate terminal:

```bash
# From aiNagisa root
uv run python backend/app.py
```

### Step 6: Select PFC Agent in Frontend

1. Open the aiNagisa frontend (http://localhost:8000)
2. Select "PFC Expert" profile from the agent selector
3. Start chatting with the PFC-enabled AI!

## Usage Examples

### Example 1: Create a Ball

In the aiNagisa chat:

```
User: Create a ball with radius 0.5 at position (0, 0, 0) with density 2500
```

The AI will use `pfc_create_ball` tool:

```python
pfc_create_ball(radius=0.5, x=0, y=0, z=0, density=2500)
```

### Example 2: Run Simulation

```
User: Run the simulation for 1000 timesteps
```

The AI will use `pfc_run_cycles` tool:

```python
pfc_run_cycles(steps=1000)
```

### Example 3: Query Model State

```
User: Show me all balls in the model
```

The AI will use `pfc_query_balls` tool:

```python
pfc_query_balls()
```

### Example 4: Execute Raw PFC Commands

```
User: Execute the PFC command to set gravity to 9.81 in z direction
```

The AI will use `pfc_execute_command` tool:

```python
pfc_execute_command(
    command="set.gravity",
    params='{"z": -9.81}'
)
```

### Example 5: Save/Load State

```
User: Save the current model state to "test_model.sav"
```

```python
pfc_save_state(filename="test_model.sav")
```

```
User: Load the model from "test_model.sav"
```

```python
pfc_load_state(filename="test_model.sav")
```

## Advanced: Running Multiple Commands

The AI can chain multiple PFC operations:

```
User: Create 10 balls with random positions and radii between 0.3 and 0.7, then run 500 cycles
```

The AI will execute multiple tool calls in sequence.

## Troubleshooting

### Server Won't Start

**Error**: `ImportError: websockets package not found`

**Solution**: Install websockets in PFC's Python environment:

```python
>>> import subprocess
>>> subprocess.run(["pip", "install", "websockets"])
```

### Connection Failed

**Error**: `Failed to connect to PFC server`

**Checklist**:
1. Is PFC GUI running?
2. Is the PFC server started in IPython shell? (`server.start_background()`)
3. Is the server listening on port 9001? (check for port conflicts)
4. Firewall blocking localhost:9001?

### ITASCA SDK Not Available

**Error**: `ITASCA SDK not available`

**Cause**: Server running outside PFC GUI environment

**Solution**: Make sure to start the server from within PFC GUI's IPython shell, not from a regular Python console.

### Commands Not Executing

**Check**:
1. View server logs in PFC IPython shell
2. Check aiNagisa backend logs for WebSocket errors
3. Verify the command syntax matches ITASCA SDK documentation

## Stopping the Server

To stop the background server in PFC IPython shell:

```python
>>> from pfc_server import server
>>> srv = server.get_server()
>>> # The server will stop when you close PFC GUI
```

Or simply close the PFC GUI application.

## Next Steps

- Explore the [PFC Tool Reference](TOOL_REFERENCE.md) for detailed tool documentation
- Check the [ITASCA SDK Documentation](https://www.itascacg.com/) for available commands
- Build custom workflows by combining multiple PFC operations

## Tips

1. **Development Mode**: Keep the PFC GUI, aiNagisa backend, and frontend all running simultaneously
2. **State Persistence**: Use `pfc_save_state` frequently to preserve your work
3. **Error Handling**: If a command fails, check the PFC IPython shell for detailed error messages
4. **Performance**: For batch operations, consider using `pfc_execute_command` with custom scripts

## Support

For issues or questions:
- Check the [main aiNagisa documentation](../README.md)
- Review ITASCA PFC official documentation
- Report bugs at https://github.com/yusong652/aiNagisa/issues
