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

# Configure logging - output to both console and file
import os
# Use os.getcwd() since __file__ is not available when using exec()
log_file = os.path.join(os.getcwd(), "pfc_server.log")

# Force configure logging (basicConfig won't work if already configured)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Clear existing handlers
root_logger.handlers.clear()
# Add handlers
formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
file_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Import server components
from server.main_thread_executor import MainThreadExecutor
from server.server import create_server

# Load configuration
try:
    from config import (  # type: ignore
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
    _config_loaded = True
except ImportError:
    # Fallback to defaults if config not found
    HOST = "localhost"
    PORT = 9001
    PING_INT = 120  # 2 minutes (long tasks friendly)
    PING_TO = 300   # 5 minutes (prevent disconnection)
    AUTO_START = False
    _config_loaded = False

# Track initialization status for summary
_init_status = {
    "config": _config_loaded,
    "pfc_state": False,
    "interrupt": False,
    "git": False,
    "git_issue": None
}

# ===== Create Main Thread Executor =====
main_executor = MainThreadExecutor()

# ===== Create Event for Task Loop Control =====
stop_event = threading.Event()

# ===== Configure PFC Python State & Register Interrupt Callback =====
# Both require itasca module - combine for cleaner flow
try:
    import itasca as it  # type: ignore

    # Prevent PFC from resetting Python state/cache on initialization
    it.command("python-reset-state false")
    _init_status["pfc_state"] = True

    # Register global callback for task interruption (must be before any script execution)
    from server.interrupt_manager import register_interrupt_callback
    _init_status["interrupt"] = register_interrupt_callback(it, position=50.0)

except ImportError:
    pass  # itasca not available - will show in summary
except Exception as e:
    logging.warning("Failed to configure PFC: {}".format(e))

# ===== Check Git Version Tracking =====
# Git snapshots are created in the user's PFC project directory (where script files are located)
# This check only verifies git is installed; actual repository detection happens at execution time
try:
    from server.git_version_manager import get_git_manager
    git_manager = get_git_manager()
    git_status = git_manager.diagnose_git_status()

    if git_status["available"] or git_status["issue"] == "not_initialized":
        _init_status["git"] = True
    else:
        _init_status["git_issue"] = git_status
except Exception as e:
    _init_status["git_issue"] = {"message": str(e), "action": None}

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
    Run continuous task processing loop.

    Args:
        interval: Check interval in seconds (default: 0.01 = 100Hz)

    Note:
        This will BLOCK the IPython prompt. Press Ctrl+C to stop.
    """
    print("Task loop running (Ctrl+C to stop)...")

    # Clear stop event before starting
    stop_event.clear()

    try:
        while not stop_event.is_set():
            main_executor.process_tasks()
            stop_event.wait(interval)
    except KeyboardInterrupt:
        print("\n✓ Loop stopped")
    finally:
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
    print()
    print("=" * 60)
    print("PFC WebSocket Server")
    print("=" * 60)
    print("  URL:         ws://{}:{}".format(HOST, PORT))
    print("  Running:     {}".format(server_thread.is_alive()))
    print("  Connections: {}".format(len(pfc_server.active_connections)))
    print("  Queue:       {} pending".format(main_executor.queue_size()))
    print("  Mode:        {}".format(processing_mode))
    print("-" * 60)
    print("Commands:")
    print("  server_status()   - Show this status")
    print("  run_task_loop()   - Continuous processing (Ctrl+C to stop)")
    print("=" * 60)
    print()

# ===== Startup Summary =====
def _print_startup_summary():
    """Print concise startup summary with status indicators."""
    print()
    print("=" * 60)
    print("PFC WebSocket Server")
    print("=" * 60)
    print("  URL:       ws://{}:{}".format(HOST, PORT))
    print("  Log:       {}".format(log_file))

    # Status indicators
    status_items = []
    if _init_status["pfc_state"]:
        status_items.append("PFC")
    if _init_status["interrupt"]:
        status_items.append("Interrupt")
    if _init_status["git"]:
        status_items.append("Git")

    if status_items:
        print("  Features:  {}".format(", ".join(status_items)))

    # Warnings
    warnings = []
    if not _init_status["config"]:
        warnings.append("config.py not found (using defaults)")
    if not _init_status["pfc_state"]:
        warnings.append("itasca module not available")
    if _init_status["git_issue"]:
        issue = _init_status["git_issue"]
        warnings.append("Git: {}".format(issue.get("message", "unavailable")))

    if warnings:
        print("-" * 60)
        for w in warnings:
            print("  ⚠ {}".format(w))

    print("-" * 60)
    print("Commands:  server_status()  run_task_loop()")
    print("=" * 60)
    print()

_print_startup_summary()

# ===== Auto-start Task Loop (if enabled) =====
if AUTO_START and processing_mode == "hook":
    print("Auto-starting task loop... (Ctrl+C to stop)")
    time.sleep(0.5)
    run_task_loop()
