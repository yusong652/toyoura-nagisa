# -*- coding: utf-8 -*-
"""
PFC WebSocket Server Startup Script (Hybrid Queue Architecture)

This version runs the WebSocket server in a BACKGROUND THREAD while keeping
IPython shell interactive. Commands are executed in the MAIN THREAD via queue
mechanism to ensure thread safety.

Architecture:
- WebSocket Server: Background thread (non-blocking, accepts connections)
- Command Execution: Main thread via queue (thread-safe for PFC)
- Task Processing: IPython post_execute hook (triggered by any IPython command)

Usage in PFC GUI IPython shell (one-line command):
    >>> import sys; sys.path.append(r'C:\\Dev\\Han\\toyoura-nagisa\\services\\pfc-server'); exec(open(r'C:\\Dev\\Han\\toyoura-nagisa\\services\\pfc-server\\start_server.py', encoding='utf-8').read())

Features:
    - IPython shell remains fully interactive (not blocked)
    - All PFC commands execute in main thread (thread-safe)
    - Task processing via IPython hook (any command triggers processing)
    - Supports callback-based commands (contact cmat, etc.)
    - Long timeout configuration for long-running tasks
    - Thread detection and logging for debugging

Python 3.6 compatible implementation.
"""

import sys
import asyncio
import logging
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Import server components
from server.main_thread_executor import MainThreadExecutor
from server.server import create_server

# Load configuration
try:
    from config import ( # type: ignore
        WEBSOCKET_HOST,
        WEBSOCKET_PORT,
        PING_INTERVAL,
        PING_TIMEOUT,
        AUTO_START_TASK_LOOP
    )
    HOST = WEBSOCKET_HOST
    PORT = WEBSOCKET_PORT
    PING_INT = PING_INTERVAL
    PING_TO = PING_TIMEOUT
    AUTO_START = AUTO_START_TASK_LOOP
except ImportError:
    # Fallback to defaults if config not found
    HOST = "localhost"
    PORT = 9001
    PING_INT = 120  # 2 minutes (long tasks friendly)
    PING_TO = 300   # 5 minutes (prevent disconnection)
    AUTO_START = False
    print("Warning: config.py not found, using default settings")

print("Initializing PFC WebSocket Server...")

# ===== Create Main Thread Executor =====
main_executor = MainThreadExecutor()

# ===== Create Event for Task Loop Control =====
stop_event = threading.Event()

# ===== Configure PFC Python State =====
# Prevent PFC from resetting Python state/cache on initialization
try:
    import itasca as it # type: ignore
    it.command("python-reset-state false")
    print("✓ Python state preservation enabled (python-reset-state false)")
except ImportError:
    print("⚠ itasca module not available - skipping python-reset-state")
except Exception as e:
    print("⚠ Failed to set python-reset-state: {}".format(e))

# ===== Create Server Instance =====
pfc_server = create_server(
    main_executor=main_executor,
    host=HOST,
    port=PORT,
    ping_interval=PING_INT,
    ping_timeout=PING_TO
)

# ===== Start Server in Background Thread =====
def run_server_background():
    """Run WebSocket server in background thread event loop."""
    # Create new event loop for background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Start server
        loop.run_until_complete(pfc_server.start())

        # Keep running
        loop.run_forever()
    except Exception as e:
        logging.error("Server error: {}".format(e))
        import traceback
        traceback.print_exc()
    finally:
        loop.close()

# Start background thread
server_thread = threading.Thread(target=run_server_background, daemon=True)
server_thread.start()

# Wait a moment for server to start
time.sleep(0.5)

# ===== Register IPython Hook for Auto Task Processing =====
try:
    from IPython import get_ipython # type: ignore

    ip = get_ipython()
    if ip:
        # Register post_execute hook (MAIN THREAD execution)
        ip.events.register('post_execute', main_executor.process_tasks)
        processing_mode = "hook"
    else:
        processing_mode = "manual"
except ImportError:
    processing_mode = "manual"

# ===== Utility Functions =====
def run_task_loop(interval=0.01):
    """
    Run continuous task processing loop (improved with threading.Event).

    This function provides an alternative task processing mode when
    IPython hooks are not sufficient or not available.

    Args:
        interval: Check interval in seconds (default: 0.01 = 100Hz)

    Note:
        This will BLOCK the IPython prompt while running, but uses
        threading.Event.wait() for better GIL release and GUI responsiveness.
        Press Ctrl+C to stop, or call stop_task_loop() from another context.

    Example:
        >>> run_task_loop()  # Start continuous processing
        >>> # Press Ctrl+C to stop
    """
    print("=" * 70)
    print("Task Processing Loop Mode (Event-based)")
    print("=" * 70)
    print("  • Interval: {:.0f}ms".format(interval * 1000))
    print("  • IPython shell BLOCKED (press Ctrl+C to stop)")
    print("  • Server continues running in background")
    print("  • Using threading.Event for better responsiveness")
    print("=" * 70)
    print()
    print("Note: GUI may take a few seconds to stabilize...")
    print()

    # Clear stop event before starting
    stop_event.clear()

    try:
        while not stop_event.is_set():
            main_executor.process_tasks()
            # Use Event.wait() instead of time.sleep() for better GIL release
            stop_event.wait(interval)
    except KeyboardInterrupt:
        print()
        print("✓ Loop stopped (Ctrl+C)")
        print("  → Tasks will now process via IPython hooks")
    finally:
        # Always clear the stop event on exit
        stop_event.clear()

def get_queue_size():
    """
    Get current task queue size.

    Returns:
        int: Number of pending tasks

    Example:
        >>> get_queue_size()
        5  # 5 tasks pending
    """
    return main_executor.queue_size()

def stop_task_loop():
    """
    Stop the running task loop gracefully.

    This function can be called from another context (e.g., a signal handler
    or another thread) to stop the task loop without using Ctrl+C.

    Example:
        >>> # In one IPython session:
        >>> run_task_loop()

        >>> # To stop programmatically (e.g., from a callback):
        >>> stop_task_loop()
    """
    if stop_event.is_set():
        print("Task loop is not running or already stopping")
    else:
        print("Stopping task loop...")
        stop_event.set()

def server_status():
    """
    Display server status and usage information.

    Example:
        >>> server_status()
    """
    print("=" * 70)
    print("PFC WebSocket Server Status")
    print("=" * 70)
    print("Server:")
    print("  • URL: ws://{}:{}".format(HOST, PORT))
    print("  • Running: {}".format(server_thread.is_alive()))
    print("  • Active Connections: {}".format(len(pfc_server.active_connections)))
    print()
    print("Task Queue:")
    print("  • Pending Tasks: {}".format(main_executor.queue_size()))
    print("  • Processing Mode: {}".format(processing_mode))
    print()
    print("Commands:")
    print("  • server_status()      - Show this status")
    print("  • get_queue_size()     - Get pending task count")
    print("  • run_task_loop()      - Run continuous processing loop (Event-based)")
    print("  • stop_task_loop()     - Stop the running loop gracefully")
    print()
    print("Trigger Task Processing:")
    print("  • Run any IPython command (e.g., pass, 1+1)")
    print("  • Or use: run_task_loop() for continuous mode")
    print("  • Improved: Event.wait() for better GUI responsiveness")
    print("=" * 70)

# ===== Startup Complete =====
print()
server_status()

# ===== Auto-start Task Loop (if enabled) =====
if AUTO_START and processing_mode == "hook":
    print()
    print("=" * 70)
    print("Auto-starting continuous task processing loop...")
    print("(Set AUTO_START_TASK_LOOP = False in config.py to disable)")
    print("=" * 70)
    time.sleep(1)  # Brief pause to allow reading the message
    run_task_loop()
