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

# ===== Setup Workspace Git =====
def _setup_workspace_git():
    """
    Initialize git repository and .gitignore if needed.

    This ensures the PFC workspace is properly set up for version tracking:
    1. If git is not initialized, run `git init`
    2. If .gitignore doesn't exist, copy the template

    Returns:
        dict: Status with 'git_initialized', 'gitignore_created', 'issue' keys
    """
    import subprocess
    import shutil

    result = {
        "git_initialized": False,
        "gitignore_created": False,
        "issue": None
    }

    cwd = os.getcwd()

    # Check if git is available
    # Note: Using stdout/stderr=PIPE instead of capture_output for Python 3.6 compatibility
    try:
        version_check = subprocess.run(
            ["git", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd
        )
        if version_check.returncode != 0:
            result["issue"] = "git not installed"
            return result
    except FileNotFoundError:
        result["issue"] = "git not found in PATH"
        return result

    # Check if git repository exists
    git_check = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd
    )

    if git_check.returncode != 0:
        # Git not initialized - initialize it
        stderr = git_check.stderr.decode('utf-8', errors='replace').strip()

        # Check for ownership issue (don't auto-init in this case)
        if "dubious ownership" in stderr:
            result["issue"] = "ownership"
            return result

        # Initialize git
        init_result = subprocess.run(
            ["git", "init"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd
        )

        if init_result.returncode == 0:
            result["git_initialized"] = True
            logging.info("Initialized git repository in: {}".format(cwd))

            # Create .gitignore BEFORE initial commit so it's included
            gitignore_path = os.path.join(cwd, ".gitignore")
            if not os.path.exists(gitignore_path):
                _create_gitignore(cwd, gitignore_path, result)

            # Create initial commit (required for pfc-executions branch to work)
            # Without this, orphan branch creation can't restore to original branch
            subprocess.run(
                ["git", "add", "-A"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd
            )
            commit_result = subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "Initial PFC workspace setup"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd
            )
            if commit_result.returncode == 0:
                logging.info("Created initial commit")
        else:
            stderr = init_result.stderr.decode('utf-8', errors='replace').strip()
            result["issue"] = "git init failed: {}".format(stderr)
            return result
    else:
        # Git already initialized - just check .gitignore
        gitignore_path = os.path.join(cwd, ".gitignore")
        if not os.path.exists(gitignore_path):
            _create_gitignore(cwd, gitignore_path, result)

    return result


def _create_gitignore(cwd, gitignore_path, result):
    """Create .gitignore file from template or inline minimal version."""
    import shutil

    # Find template file via sys.path (since __file__ is not available with exec())
    template_locations = []

    # Search in sys.path for pfc-server module
    for path in sys.path:
        if "pfc-server" in path:
            template_locations.append(
                os.path.join(path, "workspace_template", ".gitignore")
            )
        # Also check parent directories that might contain pfc-server
        potential = os.path.join(path, "services", "pfc-server", "workspace_template", ".gitignore")
        if os.path.exists(potential):
            template_locations.append(potential)

    template_found = None
    for loc in template_locations:
        if os.path.exists(loc):
            template_found = loc
            break

    if template_found:
        try:
            shutil.copy(template_found, gitignore_path)
            result["gitignore_created"] = True
            logging.info("Created .gitignore from template")
        except Exception as e:
            logging.warning("Failed to copy .gitignore template: {}".format(e))
    else:
        # Template not found - create minimal .gitignore inline
        minimal_gitignore = """# PFC Runtime Files
errorlog.txt
*.dmp
*.temp
pfc_server.log
.quick_console/
"""
        try:
            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write(minimal_gitignore)
            result["gitignore_created"] = True
            logging.info("Created minimal .gitignore")
        except Exception as e:
            logging.warning("Failed to create .gitignore: {}".format(e))


# Run workspace git setup
try:
    _git_setup = _setup_workspace_git()

    if _git_setup["issue"]:
        _init_status["git"] = False
        _init_status["git_issue"] = {"message": _git_setup["issue"], "action": None}
    else:
        _init_status["git"] = True
        if _git_setup["git_initialized"]:
            _init_status["git_auto_init"] = True
        if _git_setup["gitignore_created"]:
            _init_status["gitignore_created"] = True

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

    # Auto-setup notifications (positive feedback)
    auto_setup = []
    if _init_status.get("git_auto_init"):
        auto_setup.append("git init")
    if _init_status.get("gitignore_created"):
        auto_setup.append(".gitignore")

    if auto_setup:
        print("  Setup:     Auto-created: {}".format(", ".join(auto_setup)))

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
