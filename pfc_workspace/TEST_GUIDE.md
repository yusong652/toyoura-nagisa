# PFC Integration Testing Guide

Step-by-step guide to test the PFC WebSocket server integration.

## ✅ Prerequisites Check

Run these commands to verify setup:

```bash
# 1. Check websockets installed in PFC Python
"C:\Program Files\Itasca\PFC700\exe64\python36\python.exe" -c "import websockets; print('OK')"

# 2. Check aiNagisa environment
cd C:\Dev\Han\aiNagisa
uv run python --version
```

Both should complete without errors.

---

## 🧪 Test 1: Start PFC Server

### Option A: GUI IPython Shell

1. **Open PFC3D GUI**
2. **Open Python Shell**: Menu → `View` → `Python Shell` (or similar)
3. **Paste and execute**:

```python
import sys
sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')
from pfc_server import server
server.start_background()
```

### Option B: Command-Line Console

1. **Open Command Prompt**
2. **Launch PFC Console**:

```cmd
"C:\Program Files\Itasca\PFC700\exe64\pfc3d700_console.exe"
```

3. **At PFC prompt, enter Python mode**:

```
PFC> python
```

4. **Paste and execute**:

```python
import sys
sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')
from pfc_server import server
server.start_background()
```

### Expected Output

```
✓ ITASCA SDK loaded successfully
🚀 Starting PFC WebSocket Server on localhost:9001
✓ Server running on ws://localhost:9001
✓ Server started in background
```

**✅ Test 1 Passed** if you see the above output!

---

## 🧪 Test 2: Verify WebSocket Connection

**Keep PFC server running from Test 1!**

In a **new terminal** (Command Prompt or PowerShell):

```bash
cd C:\Dev\Han\aiNagisa
uv run python pfc_workspace/test_connection.py
```

### Expected Output

```
============================================================
PFC WebSocket Server Connection Test
============================================================
Connecting to: ws://localhost:9001

✓ Connected to PFC server!

Test 1: Sending ping...
✓ Ping successful! Response: {'type': 'pong', 'timestamp': '...'}

Test 2: Sending test command...
Command response:
  Status: success (or error if no balls in model)
  Message: ...

============================================================
✓ Connection test completed successfully!
============================================================
```

**✅ Test 2 Passed** if connection succeeds and ping works!

---

## 🧪 Test 3: Test PFC Commands

**Keep PFC server running!**

In PFC Python shell (where server is running), you can still use PFC normally:

```python
# Import itasca in same shell
import itasca

# Create a ball
itasca.command("ball create radius 0.5 position (0,0,0)")

# Check number of balls
print("Number of balls:", itasca.ball.count())
```

The server runs in background, so PFC is still fully usable!

**✅ Test 3 Passed** if PFC commands work while server runs!

---

## 🧪 Test 4: Test aiNagisa Backend Integration

**Keep PFC server running!**

### Start aiNagisa Backend

In a **new terminal**:

```bash
cd C:\Dev\Han\aiNagisa
uv run python backend/app.py
```

Expected output should include:
```
[DEBUG] Registered PFC tool: pfc_execute_command
[DEBUG] Registered PFC tool: pfc_create_ball
...
[DEBUG] All 6 PFC tools registered
```

### Start Frontend

In **another terminal**:

```bash
cd C:\Dev\Han\aiNagisa\frontend
npm run dev
```

### Test in Browser

1. Open http://localhost:5173 (or port shown by Vite)
2. **Select PFC Expert Profile** (purple ⚛️ icon)
3. **Send test message**:

```
Create a ball with radius 0.5
```

### Expected Behavior

The AI should:
1. Recognize this as a PFC operation
2. Use the `pfc_create_ball` tool
3. Send WebSocket command to PFC server
4. Receive result
5. Show success message

**Check PFC server logs** - you should see:

```
✓ Client connected: 127.0.0.1:xxxxx
Executing command: ball.create with params: {'radius': 0.5, ...}
✓ Command result sent: <uuid>
```

**Check PFC model** - a ball should actually be created!

```python
# In PFC shell
print(itasca.ball.count())  # Should show 1 ball
```

**✅ Test 4 Passed** if AI successfully creates ball in PFC!

---

## 🧪 Test 5: Advanced Commands

Try these in aiNagisa chat:

### Test 5A: Run Simulation

```
Run 100 simulation cycles
```

Should use `pfc_run_cycles` tool.

### Test 5B: Query Model

```
Show me all balls in the model
```

Should use `pfc_query_balls` tool and display ball information.

### Test 5C: Save State

```
Save the current model state to "test.sav"
```

Should use `pfc_save_state` tool.

**✅ Test 5 Passed** if all commands execute successfully!

---

## 🎉 Success Criteria

All tests passed if:

- ✅ PFC server starts without errors
- ✅ WebSocket connection successful
- ✅ PFC commands work while server runs
- ✅ aiNagisa backend recognizes PFC tools
- ✅ Frontend can trigger PFC operations
- ✅ Commands actually affect PFC model

---

## 🐛 Troubleshooting

### Test 1 Fails: Server won't start

**Error**: `ModuleNotFoundError: No module named 'websockets'`

**Solution**:
```bash
"C:\Program Files\Itasca\PFC700\exe64\python36\python.exe" -m pip install websockets
```

**Error**: `AttributeError: module 'asyncio' has no attribute 'get_running_loop'`

**Solution**: Already fixed in latest server.py. Reload the module:
```python
import importlib
import pfc_server.server
importlib.reload(pfc_server.server)
from pfc_server import server
server.start_background()
```

### Test 2 Fails: Connection timeout

**Cause**: PFC server not running

**Solution**: Complete Test 1 first, ensure server is running

### Test 4 Fails: Tools not registered

**Check backend logs**: Should show "Registered PFC tool: ..." messages

**Solution**: Restart backend after installing dependencies:
```bash
uv sync  # Ensure workspace is synced
uv run python backend/app.py
```

### PFC Server Logs Show Errors

**Error**: `itasca module not available`

**Cause**: Server running outside PFC environment

**Solution**: Start server from PFC Python shell, not standalone Python

---

## 📊 Test Results Template

Copy this and fill in your results:

```
=== PFC Integration Test Results ===

Test 1: PFC Server Startup
[ ] Passed  [ ] Failed
Notes: ___________________________________

Test 2: WebSocket Connection
[ ] Passed  [ ] Failed
Notes: ___________________________________

Test 3: PFC Commands While Server Running
[ ] Passed  [ ] Failed
Notes: ___________________________________

Test 4: aiNagisa Backend Integration
[ ] Passed  [ ] Failed
Notes: ___________________________________

Test 5: Advanced Commands
[ ] Passed  [ ] Failed
Notes: ___________________________________

Overall Status: [ ] All Passed  [ ] Some Failed

Issues encountered:
_________________________________________
_________________________________________
```

---

## 🔄 Next Steps After Testing

If all tests pass:

1. **Commit changes** to git
2. **Update main README.md** with PFC integration info
3. **Create example workflows** for common PFC tasks
4. **Add more PFC-specific tools** as needed

If tests fail:

1. **Document the error** in test results template
2. **Check logs** in PFC server and aiNagisa backend
3. **Report issues** with full error messages
4. **Review DEPLOYMENT.md** for alternative approaches
