# PFC Server Deployment Guide

Complete guide for deploying the PFC WebSocket server in different environments.

## 🚀 Deployment Options

### Option 1: PFC GUI IPython Shell (Interactive Development)

**Best for**: Interactive modeling, debugging, real-time experimentation

**Steps**:
1. Open PFC GUI application
2. Open IPython shell (`View → Python Shell`)
3. Run startup script:

```python
>>> import sys
>>> sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')
>>> from pfc_server import server
>>> server.start_background()  # Non-blocking
```

**Advantages**:
- ✅ Full GUI access while server runs
- ✅ Can visualize model in real-time
- ✅ Interactive debugging in IPython
- ✅ Easy to inspect itasca objects

**Disadvantages**:
- ❌ Requires GUI (high memory usage)
- ❌ Can't run headless
- ❌ GUI crashes = server crashes

---

### Option 2: PFC Console Python Mode (Lightweight Interactive)

**Best for**: Lighter-weight interactive use, server-focused operation

**Steps**:
1. Open PFC console:
   ```bash
   "C:\Program Files\Itasca\PFC700\exe64\pfc3d700_console.exe"
   ```

2. Enter Python mode:
   ```
   PFC> python
   ```

3. Run startup commands:
   ```python
   >>> import sys
   >>> sys.path.append(r'C:\Dev\Han\aiNagisa\pfc_workspace')
   >>> from pfc_server import server
   >>> server.start_background()
   ```

**Advantages**:
- ✅ Lighter than GUI (less memory)
- ✅ Can still interact with PFC
- ✅ Terminal-based, scriptable
- ✅ Full itasca module access

**Disadvantages**:
- ❌ No visualization
- ❌ Still requires PFC console running
- ❌ Manual startup steps

---

### Option 3: PFC Startup Script (Automated Console)

**Best for**: Automated deployment, production use

**Steps**:

1. **First time only** - Install websockets:
   ```bash
   "C:\Program Files\Itasca\PFC700\exe64\python36\python.exe" -m pip install websockets
   ```

2. Create a `.pfc` command file:

   **File**: `C:\Dev\Han\aiNagisa\pfc_workspace\startup.pfc`
   ```
   ; PFC startup file to launch WebSocket server
   python call C:\Dev\Han\aiNagisa\pfc_workspace\start_server.py
   ```

3. Launch PFC with the startup file:
   ```bash
   "C:\Program Files\Itasca\PFC700\exe64\pfc3d700_console.exe" startup.pfc
   ```

**Advantages**:
- ✅ One-command startup
- ✅ Scriptable and automatable
- ✅ Can run as Windows service
- ✅ Full itasca module access

**Disadvantages**:
- ❌ Still requires PFC console process
- ❌ Less interactive
- ❌ Harder to debug startup issues

---

### Option 4: Standalone Python Script (Testing Only)

**Best for**: Testing server logic without PFC

**Steps**:

1. Install websockets in PFC Python:
   ```bash
   "C:\Program Files\Itasca\PFC700\exe64\python36\python.exe" -m pip install websockets
   ```

2. Run standalone:
   ```bash
   "C:\Program Files\Itasca\PFC700\exe64\python36\python.exe" C:\Dev\Han\aiNagisa\pfc_workspace\start_server.py
   ```

**Result**:
```
✓ websockets module available
⚠ itasca module not available - running outside PFC
  Server will work but commands will fail until run in PFC environment
```

**Advantages**:
- ✅ Test server connectivity without PFC
- ✅ Fast startup for development
- ✅ Can test WebSocket protocol

**Disadvantages**:
- ❌ itasca module not available
- ❌ All PFC commands will fail
- ❌ Only useful for connectivity testing

---

## 📋 Comparison Table

| Deployment Option | itasca Available | Memory Usage | Automation | Visualization |
|-------------------|------------------|--------------|------------|---------------|
| GUI IPython Shell | ✅ Yes | High | Manual | ✅ Full GUI |
| Console Python    | ✅ Yes | Medium | Manual | ❌ No |
| Startup Script    | ✅ Yes | Medium | ✅ Automated | ❌ No |
| Standalone Python | ❌ No | Low | ✅ Automated | ❌ No |

## 🎯 Recommended Workflow

### Development Phase
Use **Option 1 (GUI IPython Shell)** for:
- Model development
- Testing new tools
- Visual debugging
- Interactive experiments

### Production/Automation
Use **Option 3 (Startup Script)** for:
- Continuous operation
- Server deployments
- Automated workflows
- CI/CD integration

### Testing
Use **Option 4 (Standalone)** for:
- WebSocket protocol testing
- Server logic debugging
- Connection testing without PFC overhead

## 🔧 Advanced Configuration

### Running as Windows Service

Create a Windows service wrapper for automated startup:

1. Install NSSM (Non-Sucking Service Manager):
   ```bash
   choco install nssm
   ```

2. Create service:
   ```bash
   nssm install PFCServer "C:\Program Files\Itasca\PFC700\exe64\pfc3d700_console.exe" startup.pfc
   nssm set PFCServer AppDirectory "C:\Dev\Han\aiNagisa\pfc_workspace"
   nssm set PFCServer DisplayName "PFC WebSocket Server"
   nssm set PFCServer Description "ITASCA PFC WebSocket server for aiNagisa integration"
   ```

3. Start service:
   ```bash
   nssm start PFCServer
   ```

### Docker Deployment (Future)

**Note**: Currently challenging due to PFC licensing requirements and Windows-only binaries. Future work could explore:
- Windows containers
- License server configuration
- Headless PFC deployment

### Environment Variables

Configure server through environment variables:

```bash
set PFC_SERVER_HOST=0.0.0.0
set PFC_SERVER_PORT=9001
set PFC_SERVER_LOG_LEVEL=DEBUG

"C:\Program Files\Itasca\PFC700\exe64\pfc3d700_console.exe" startup.pfc
```

Update `pfc_server/server.py` to read from `os.environ`.

## 🐛 Troubleshooting Deployment

### "websockets module not found"

**Solution**: Install in PFC's Python environment:
```bash
"C:\Program Files\Itasca\PFC700\exe64\python36\python.exe" -m pip install websockets
```

### "itasca module not available"

**Cause**: Running outside PFC environment

**Solution**: Use Option 1, 2, or 3 (not Option 4)

### Server starts but commands fail

**Check**:
1. Is `itasca` module available? (print in startup)
2. Are you in PFC Python environment? (not standalone)
3. Check PFC console logs for errors

### Port 9001 already in use

**Solution**: Change port in `start_server.py`:
```python
server.start(port=9002)  # Use different port
```

Update aiNagisa backend client URL accordingly.

### PFC console doesn't respond after startup

**Cause**: Using blocking mode (`server.start()`)

**Solution**: Use non-blocking mode:
```python
server.start_background()  # Returns immediately
```

## 📊 Monitoring

### Check Server Status

From another Python console:

```python
import asyncio
import websockets

async def ping_server():
    async with websockets.connect("ws://localhost:9001") as ws:
        await ws.send('{"type": "ping"}')
        response = await ws.recv()
        print(response)

asyncio.run(ping_server())
```

Expected output:
```json
{"type": "pong", "timestamp": "2025-10-02T..."}
```

### View Server Logs

In PFC console/shell where server is running, all logs appear in stdout:
```
✓ ITASCA SDK loaded successfully
🚀 Starting PFC WebSocket Server on localhost:9001
✓ Server running on ws://localhost:9001
✓ Client connected: 127.0.0.1:52341
Executing command: ball.create with params: {'radius': 0.5}
✓ Command result sent: test-123
```

## 🔒 Security Considerations

### Localhost Only (Default)

Server binds to `localhost` (127.0.0.1) by default - only accepts local connections.

**Safe for**: Single-machine development

### Network Access (Advanced)

To allow remote connections:

```python
server.start(host="0.0.0.0")  # Listen on all interfaces
```

**⚠️ Security Risks**:
- No authentication
- No encryption
- Direct PFC command execution

**Recommendations**:
- Use firewall rules to restrict access
- Consider SSH tunneling for remote access
- Add authentication in production

### SSH Tunnel for Remote Access

Safe remote access via SSH tunnel:

```bash
# On remote machine
ssh -L 9001:localhost:9001 user@pfc-server

# Now connect to localhost:9001 on remote machine
# Traffic is encrypted through SSH
```

## 📚 Further Reading

- [QUICKSTART.md](QUICKSTART.md) - Basic setup guide
- [TOOL_REFERENCE.md](TOOL_REFERENCE.md) - Available tools
- [../README.md](README.md) - Architecture overview
- [ITASCA PFC Documentation](https://www.itascacg.com/software/pfc) - Official docs
