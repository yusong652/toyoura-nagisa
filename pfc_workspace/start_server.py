# -*- coding: utf-8 -*-
"""
PFC WebSocket Server Startup Script (Main Thread Version)

IMPORTANT: This version runs the server in the MAIN THREAD, which blocks
the IPython shell but ensures all PFC commands execute in the correct thread context.
This is required for commands like 'contact cmat default' that crash when executed
in background threads.

Usage in PFC GUI IPython shell:
    >>> import sys
    >>> sys.path.append(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace')
    >>> exec(open(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace\\start_server.py', encoding='utf-8').read())

Note:
    - IPython shell will be BLOCKED while server runs (this is intentional)
    - Server output will be visible in PFC Console
    - To stop server: Press Ctrl+C or close PFC GUI
    - You can observe PFC state through GUI visualization while server runs
"""

import sys
import asyncio
import logging
import nest_asyncio # type: ignore

# Allow nested event loops (required for IPython environment)
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    stream=sys.stdout
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
    PING_TO = 10
    print("Warning: config.py not found, using default settings")

print("=" * 60)
print("PFC WebSocket Server (Main Thread Mode)")
print("=" * 60)
print()
print("⚠ WARNING: This will BLOCK the IPython shell")
print("⚠ Server runs in main thread for thread-safe PFC commands")
print()
print(f"Starting server on: ws://{HOST}:{PORT}")
print("To stop: Press Ctrl+C or close PFC GUI")
print("=" * 60)
print()

# Create server instance
pfc_server = create_server(
    host=HOST,
    port=PORT,
    ping_interval=PING_INT,
    ping_timeout=PING_TO
)

# Get the current event loop (IPython's existing loop)
# nest_asyncio allows us to use run_until_complete even if loop is already running
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    # If no loop exists, create one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

print(f"✓ Using event loop: {loop}")
print(f"✓ Loop is running: {loop.is_running()}")
print()

async def keep_server_running():
    """Keep server running with periodic yields for GUI updates."""
    # Start server
    await pfc_server.start()

    print("✓ Server is running on ws://{}:{}".format(HOST, PORT))
    print()
    print("IMPORTANT:")
    print("  • IPython shell is BLOCKED (this is necessary)")
    print("  • PFC GUI should still be responsive")
    print("  • Server logs will appear in console")
    print("  • Press Ctrl+C to stop")
    print()

    # Keep running with frequent yields for GUI updates
    try:
        while True:
            # Yield control frequently to allow PFC GUI updates
            await asyncio.sleep(0.05)  # 50ms intervals
    except asyncio.CancelledError:
        print("\n✓ Server shutdown requested")

try:
    print("✓ Server starting...")
    # Run server with event loop (will block IPython but allow GUI updates)
    loop.run_until_complete(keep_server_running())

except KeyboardInterrupt:
    print("\n✓ Server stopped by user (Ctrl+C)")
except Exception as e:
    print(f"\n✗ Server error: {e}")
    import traceback
    traceback.print_exc()
finally:
    print("✓ Server shutdown complete")
    print("=" * 60)
