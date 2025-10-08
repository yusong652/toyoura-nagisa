# -*- coding: utf-8 -*-
"""
PFC WebSocket Server Startup Script (Background Thread Mode)

This version runs the WebSocket server in a BACKGROUND THREAD, keeping the
IPython shell and PFC GUI fully responsive. Main thread commands (like
'contact cmat default') are executed via PFC callback mechanism.

Usage in PFC GUI IPython shell:
    >>> import sys
    >>> sys.path.append(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace')
    >>> exec(open(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace\\start_server_background.py', encoding='utf-8').read())

Advantages:
    - IPython shell remains AVAILABLE for interactive use
    - PFC GUI remains RESPONSIVE (can see visualizations update)
    - Real-time logs visible in console
    - All main thread commands execute safely via callback mechanism
"""

import sys
import threading
import asyncio
import logging
import nest_asyncio

# Allow nested event loops (helps with IPython compatibility)
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pfc_server.log', mode='a', encoding='utf-8')
    ]
)

# Import server
from pfc_server.server import create_server

# Load configuration
try:
    from config import (
        WEBSOCKET_HOST,
        WEBSOCKET_PORT,
        PING_INTERVAL,
        PING_TIMEOUT
    )
    HOST = WEBSOCKET_HOST
    PORT = WEBSOCKET_PORT
    PING_INT = PING_INTERVAL
    PING_TO = PING_TIMEOUT
except ImportError:
    # Fallback to defaults if config not found
    HOST = "localhost"
    PORT = 9001
    PING_INT = 30
    PING_TO = 60
    print("Warning: config.py not found, using default settings")

print("=" * 70)
print("PFC WebSocket Server (Background Thread Mode)")
print("=" * 70)
print()
print("✓ Server will run in BACKGROUND THREAD")
print("✓ IPython shell will remain AVAILABLE")
print("✓ PFC GUI will remain RESPONSIVE")
print("✓ Main thread commands execute via callback mechanism")
print()
print(f"Starting server on: ws://{HOST}:{PORT}")
print("=" * 70)
print()

# Create server instance
pfc_server = create_server(
    host=HOST,
    port=PORT,
    ping_interval=PING_INT,
    ping_timeout=PING_TO
)

def run_server_in_background():
    """
    Run WebSocket server in background thread.

    Creates a new event loop for the background thread and runs
    the server there. This keeps the main thread (IPython/GUI) free.
    """
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Start server
        loop.run_until_complete(pfc_server.start())

        print("✓ Server started in background thread")
        print("✓ IPython shell is now available for use")
        print("✓ PFC GUI should remain responsive")
        print()
        print("Logs will appear below as commands are executed...")
        print("=" * 70)
        print()

        # Keep server running
        loop.run_forever()

    except KeyboardInterrupt:
        print("\n✓ Server stopped by KeyboardInterrupt")
    except Exception as e:
        print(f"\n✗ Server error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.close()

# Start server in background thread (daemon=True means it will exit when main program exits)
server_thread = threading.Thread(target=run_server_in_background, daemon=True, name="PFC-WebSocket-Server")
server_thread.start()

# Brief pause to let server start
import time
time.sleep(0.5)

print("=" * 70)
print("Server Status Summary:")
print("=" * 70)
print(f"  • Server: Running on ws://{HOST}:{PORT}")
print(f"  • Thread: {server_thread.name} (background, daemon)")
print("  • IPython: Available for interactive use")
print("  • PFC GUI: Responsive (not blocked)")
print("  • Logs: Writing to console and pfc_server.log")
print("=" * 70)
print()
print("You can now:")
print("  - Run commands in IPython")
print("  - Observe PFC GUI visualizations")
print("  - Send commands via WebSocket client")
print()
print("To stop server: Close PFC GUI or restart Python kernel")
print("=" * 70)
