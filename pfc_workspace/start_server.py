#!/usr/bin/env python
"""
PFC Server Startup Script

This script can be run in multiple ways:

1. From PFC Console Python mode:
   PFC> python
   >>> exec(open('start_server.py').read())

2. From PFC Console command:
   PFC> python call start_server.py

3. From PFC standalone Python:
   C:\Program Files\Itasca\PFC700\exe64\python36\python.exe start_server.py

4. With custom Python path:
   python start_server.py
"""

import sys
import os

# Add pfc_workspace to path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

print("=" * 60)
print("PFC WebSocket Server Startup")
print("=" * 60)
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Script directory: {script_dir}")
print()

# Try to import itasca
try:
    import itasca
    print("✓ itasca module available - running in PFC environment")
    itasca_available = True
except ImportError:
    print("⚠ itasca module not available - running outside PFC")
    print("  Server will work but commands will fail until run in PFC environment")
    itasca_available = False

print()

# Check for websockets
try:
    import websockets
    print("✓ websockets module available")
except ImportError:
    print("✗ websockets module not found!")
    print()
    print("Please install websockets:")
    print("  pip install websockets")
    print()
    print("Or with PFC Python:")
    print('  "C:\\Program Files\\Itasca\\PFC700\\exe64\\python36\\python.exe" -m pip install websockets')
    sys.exit(1)

print()

# Import and start server
try:
    from pfc_server import server

    print("Starting PFC WebSocket Server...")
    print("Server will listen on: ws://localhost:9001")
    print()
    print("To stop the server: Press Ctrl+C")
    print("=" * 60)
    print()

    # Start in foreground mode (easier to stop)
    server.start()

except KeyboardInterrupt:
    print("\n✓ Server stopped by user")
except Exception as e:
    print(f"\n✗ Server failed to start: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
