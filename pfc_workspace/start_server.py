# -*- coding: utf-8 -*-
"""
PFC Server Startup - Uses threading for Python 3.6 compatibility.

RECOMMENDED: Set workspace path in config.py, then run:
    >>> import sys
    >>> sys.path.append(r'AINAGISA_ROOT\\pfc_workspace')
    >>> exec(open(r'AINAGISA_ROOT\\pfc_workspace\\start_server.py', encoding='utf-8').read())
"""

import sys
import threading
import os

# Determine workspace path
try:
    # When run directly with python start_server.py
    workspace = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # When run via exec(), __file__ doesn't exist
    # Assume the user already added the workspace to sys.path
    # Try to find pfc_server module to determine workspace
    workspace = None
    for path in sys.path:
        if os.path.exists(os.path.join(path, 'pfc_server')):
            workspace = path
            break

    if workspace is None:
        print("ERROR: Cannot find pfc_workspace in Python path!")
        print("")
        print("Please add workspace to sys.path first:")
        print("    >>> import sys")
        print("    >>> sys.path.append(r'C:\\\\Dev\\\\Han\\\\aiNagisa\\\\pfc_workspace')")
        print("    >>> exec(open(r'...\\\\start_server.py', encoding='utf-8').read())")
        print("")
        print("Or use the simpler approach:")
        print("    >>> import sys; sys.path.append(r'C:\\\\Dev\\\\Han\\\\aiNagisa\\\\pfc_workspace')")
        print("    >>> from pfc_server import server; server.start_background()")
        raise SystemExit("Workspace not in Python path")

# Add workspace to path first
if workspace not in sys.path:
    sys.path.insert(0, workspace)

# Try to load config to get correct workspace path
try:
    from config import PFC_WORKSPACE_PATH
    # Use config path if different
    if PFC_WORKSPACE_PATH != workspace:
        workspace = PFC_WORKSPACE_PATH
        if workspace not in sys.path:
            sys.path.insert(0, workspace)
except ImportError:
    # config.py doesn't exist, but we can still work with hardcoded path
    pass

print("=" * 60)
print("PFC WebSocket Server - Simple Startup")
print("=" * 60)

# Check itasca
try:
    import itasca # type: ignore
    print("Itasca module available")
except ImportError:
    print("Warning: itasca module not found (commands will fail)")

# Check websockets
try:
    import websockets
    print("✓ websockets module available")
except ImportError:
    print("✗ Error: websockets not installed")
    print("  Install with: pip install websockets")
    raise SystemExit("Missing required dependency: websockets")

print()

# Import server
from pfc_server import server

def run_server():
    """Run server in thread."""
    try:
        server.start()  # Blocking call
    except KeyboardInterrupt:
        print("\nServer stopped")
    except Exception as e:
        print(f"\nServer error: {e}")
        import traceback
        traceback.print_exc()

# Start server in daemon thread
print("Starting server in background thread...")
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

print("Server thread started")
print()
print("Server running on: ws://localhost:9001")
print("You can now use PFC normally while server runs!")
print()
print("To stop: Close PFC or press Ctrl+C in this shell")
print("=" * 60)
