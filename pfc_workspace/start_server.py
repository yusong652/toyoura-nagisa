# -*- coding: utf-8 -*-
"""
PFC WebSocket Server Startup Script

Usage in PFC GUI IPython shell:
    >>> import sys
    >>> sys.path.append(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace')
    >>> exec(open(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace\\start_server.py', encoding='utf-8').read())
"""

import sys
import threading
import asyncio
import logging

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
print("PFC WebSocket Server")
print("=" * 60)

# Create server instance
pfc_server = create_server(
    host=HOST,
    port=PORT,
    ping_interval=PING_INT,
    ping_timeout=PING_TO
)

def run_server():
    """Run async server in background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Start the server (returns immediately after setup)
        loop.run_until_complete(pfc_server.start())

        # Run event loop forever to handle connections
        # This allows the event loop to process WebSocket connections
        loop.run_forever()
    except KeyboardInterrupt:
        print("\n✗ Server stopped by user")
    except Exception as e:
        print(f"\n✗ Server error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.close()

# Start server in daemon thread
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

print(f"✓ Server running on: ws://{HOST}:{PORT}")
print("✓ You can now use PFC normally while server runs")
print()
print("To stop: Close PFC (daemon thread auto-terminates)")
print("=" * 60)
