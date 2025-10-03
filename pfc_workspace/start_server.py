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

# Server configuration
HOST = "localhost"
PORT = 9001

print("=" * 60)
print("PFC WebSocket Server")
print("=" * 60)

# Create server instance
pfc_server = create_server(host=HOST, port=PORT)

def run_server():
    """Run async server in background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(pfc_server.start())
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
