# -*- coding: utf-8 -*-
"""
Simplified PFC Server Startup - Uses threading for Python 3.6 compatibility.

Run this in PFC Python shell:
    >>> exec(open(r'C:\Dev\Han\aiNagisa\pfc_workspace\start_simple.py', encoding='utf-8').read())
"""

import sys
import threading
import os

# Add workspace to path (handle both direct execution and exec())
try:
    workspace = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # When run via exec(), __file__ doesn't exist
    workspace = r'C:\Dev\Han\aiNagisa\pfc_workspace'

if workspace not in sys.path:
    sys.path.insert(0, workspace)

print("=" * 60)
print("PFC WebSocket Server - Simple Startup")
print("=" * 60)

# Check itasca
try:
    import itasca
    print("✓ itasca module available")
except ImportError:
    print("⚠ Warning: itasca module not found (commands will fail)")

# Check websockets
try:
    import websockets
    print("✓ websockets module available")
except ImportError:
    print("✗ Error: websockets not installed")
    print("  Install with: pip install websockets")
    sys.exit(1)

print()

# Import server
from pfc_server import server

def run_server():
    """Run server in thread."""
    try:
        server.start()  # Blocking call
    except KeyboardInterrupt:
        print("\n✓ Server stopped")
    except Exception as e:
        print(f"\n✗ Server error: {e}")
        import traceback
        traceback.print_exc()

# Start server in daemon thread
print("Starting server in background thread...")
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

print("✓ Server thread started")
print()
print("Server running on: ws://localhost:9001")
print("You can now use PFC normally while server runs!")
print()
print("To stop: Close PFC or press Ctrl+C in this shell")
print("=" * 60)
