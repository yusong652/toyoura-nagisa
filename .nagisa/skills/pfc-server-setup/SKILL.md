---
name: pfc-server-setup
description: >
  Complete PFC integration lifecycle: (1) Detect PFC installation path on Windows,
  (2) Check/install websockets==9.1 in PFC's Python 3.6 environment (automated via
  PFC Python executable), (3) Launch PFC GUI using PowerShell Start-Process (NOT
  'start' command which blocks in git bash), (4) Guide user to start pfc-server in
  PFC IPython console with run_loop(). Triggers: "open PFC", "start PFC", "connect
  to PFC", "pfc-server connection failed", first-time PFC setup.
---

# PFC Server Setup

Complete guide for PFC integration: environment setup, GUI launch, and pfc-server start.

---

## Architecture Overview

| Component | Environment | Role |
|-----------|-------------|------|
| toyoura-nagisa backend | UV Python 3.10+ | Sends commands via WebSocket |
| pfc-server | PFC embedded Python 3.6 | Receives commands, calls itasca SDK |
| itasca SDK | PFC internal | Executes PFC operations |

**Communication**: Backend → WebSocket (port 9001) → pfc-server → itasca SDK

**Key point**: pfc-server runs INSIDE PFC GUI process, bridging Nagisa commands to itasca SDK.

---

## Step 1: Detect PFC Installation

**Windows - quick check**:
```bash
dir "C:/Program Files/Itasca"
```

**Windows - search entire drive** (if not in default location):
```bash
powershell -Command "Get-ChildItem -Path 'C:\' -Filter 'pfc*_gui.exe' -Recurse -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 3 DirectoryName"
```

**Windows - search multiple drives**:
```bash
powershell -Command "Get-ChildItem -Path 'C:\','D:\' -Filter 'pfc*_gui.exe' -Recurse -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 3 DirectoryName"
```

**Common PFC paths**:
- `C:\Program Files\Itasca\PFC700\` (PFC 7.0)
- `C:\Program Files\Itasca\PFC600\` (PFC 6.0)

**If not found**: Ask user for PFC installation path.

---

## Step 2: Check websockets Installation

Use `{pfc_path}` from Step 1 (e.g., `C:\Program Files\Itasca\PFC700`).

**Check via PFC Python** (recommended):
```bash
"{pfc_path}/exe64/python36/python.exe" -c "import pip; pip.main(['show', 'websockets'])"
```

If output shows `Name: websockets` and `Version: 9.1`, websockets is installed.

**Alternative - check user site-packages**:
```bash
powershell -Command "Test-Path \"$env:APPDATA\Python\Python36\site-packages\websockets\""
```

---

## Step 3: Install websockets (Automated)

If websockets not found, **Nagisa can install it directly** using PFC's Python:

```bash
"{pfc_path}/exe64/python36/python.exe" -c "import pip; pip.main(['install', '--user', 'websockets==9.1'])"
```

**Why websockets==9.1?**
- PFC uses Python 3.6.1
- websockets 9.1 is the last version supporting Python 3.6
- Newer versions require Python 3.7+

### Fallback: Manual Installation

If automated install fails (permission issues, environment problems), instruct user to run in **PFC GUI IPython console**:

```python
import pip
pip.main(['install', '--user', 'websockets==9.1'])
```

**After install**: User should restart PFC GUI to ensure the module is loaded.

---

## Step 4: Locate toyoura-nagisa Project

**Windows - search for pfc-server directory**:
```bash
powershell -Command "Get-ChildItem -Path 'C:\','D:\' -Directory -Filter 'pfc-server' -Recurse -Depth 5 -ErrorAction SilentlyContinue | Select-Object -First 3 FullName"
```

**Infer project path**: If found at `X:\...\services\pfc-server`, then project is `X:\...\` (parent of `services`).

**Verify with key file**:
```python
import os
project_path = r"{project_path}"  # Inferred from search
start_script = os.path.join(project_path, "services", "pfc-server", "start_server.py")
print(f"start_server.py exists: {os.path.exists(start_script)}")
```

**If not found**: Ask user for toyoura-nagisa project path.

---

## Step 5: Launch PFC with Auto-Start (Recommended)

**Nagisa can launch PFC with auto_start_server.dat** which opens the startup script:

```bash
powershell -Command "Start-Process '{pfc_path}/exe64/pfc3d700_gui.exe' -ArgumentList '{project_path}/services/pfc-server/auto_start_server.dat'"
```

After PFC loads:
1. Script opens in Editor pane automatically
2. User clicks **Execute** button
3. Server starts and enters `run_loop()` automatically

**Success indicator**: Console shows "PFC WebSocket Server started on port 9001".

### Alternative: Manual Launch

If auto-start doesn't work, use separate steps:

```bash
powershell -Command "Start-Process '{pfc_path}/exe64/pfc3d700_gui.exe'"
```

Then user runs in **PFC GUI IPython console**:
```python
%run "{project_path}/services/pfc-server/start_server.py"
```

**Note**: `run_loop()` is called automatically (AUTO_START=True by default).

---

## Step 6: Verify Connection

After pfc-server starts, verify from Nagisa:

```python
# Use any PFC tool to test connection
pfc_list_tasks()
```

If successful, PFC integration is ready.

---

## Troubleshooting

### "No module named websockets"
Try automated install first (Step 3). If fails, use manual fallback in PFC GUI.

### "Connection refused" on port 9001
pfc-server not running. User needs to start it in PFC GUI (Step 5).

### Server starts but immediately exits
User forgot `run_loop()`. The `start_server.py` script includes this, but if running manually, ensure the event loop keeps running.

### "Address already in use"
Another pfc-server instance is running. Close PFC and restart, or find and kill the process.

### Automated install fails with permission error
Use manual fallback in PFC GUI IPython console.

---

## Quick Reference

| Step | Executor | Command |
|------|----------|---------|
| Check websockets | Nagisa | `"{pfc_path}/.../python.exe" -c "import pip; pip.main(['show', 'websockets'])"` |
| Install websockets | Nagisa | `"{pfc_path}/.../python.exe" -c "import pip; pip.main(['install', '--user', 'websockets==9.1'])"` |
| Launch + Auto-open | Nagisa | `powershell Start-Process '{pfc_path}/.../pfc3d700_gui.exe' -ArgumentList '{project_path}/.../auto_start_server.dat'` |
| Execute script | User | Click **Execute** button in PFC Editor pane |
