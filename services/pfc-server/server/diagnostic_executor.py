"""
Diagnostic Executor - Callback-based script execution for diagnostic operations.

This module provides a mechanism to execute diagnostic scripts (like plot capture)
even when PFC main thread is blocked by cycle() computation. It uses PFC's
callback system to execute scripts in the gaps between cycles.

Key Design:
- Uses global variables to pass script path to parameterless callback
- Callback executes at position 51.0 (after interrupt check at 50.0)
- Supports both cycle-blocked and cycle-free execution scenarios

Architecture:
- WebSocket thread: calls submit_diagnostic(script_path)
- PFC callback: _pfc_diagnostic_callback() reads global and executes
- Result returned via Future object

Python 3.6 compatible implementation.
"""

import threading
import logging
from concurrent.futures import Future
from typing import Any, Dict, Optional

# Module logger
logger = logging.getLogger("PFC-Server")


# =============================================================================
# Global State (Parameter channel for parameterless callback)
# =============================================================================

# Pending diagnostic script path
_pending_script_path = None  # type: Optional[str]

# Future for returning result to caller
_pending_future = None  # type: Optional[Future]

# Lock for thread-safe access
_pending_lock = threading.Lock()


# =============================================================================
# External Interface (Called from WebSocket thread)
# =============================================================================

def submit_diagnostic(script_path):
    # type: (str) -> Future
    """
    Submit diagnostic script for callback execution.

    Called from WebSocket handler thread. The script will be executed
    by PFC callback during next cycle gap.

    Args:
        script_path: Absolute path to Python script file

    Returns:
        Future: Future object to await execution result

    Example:
        future = submit_diagnostic("/path/to/capture_plot.py")
        result = future.result(timeout=30)  # Wait up to 30 seconds
    """
    global _pending_script_path, _pending_future

    future = Future()

    with _pending_lock:
        # Check if another diagnostic is pending
        if _pending_script_path is not None:
            # Previous diagnostic not yet executed - this shouldn't happen often
            logger.warning("Previous diagnostic pending, replacing: {}".format(
                _pending_script_path
            ))

        _pending_script_path = script_path
        _pending_future = future

    logger.debug("Diagnostic submitted: {}".format(script_path))
    return future


def is_diagnostic_pending():
    # type: () -> bool
    """Check if a diagnostic script is pending execution."""
    return _pending_script_path is not None


def clear_pending_diagnostic():
    # type: () -> None
    """Clear pending diagnostic (for cleanup/reset)."""
    global _pending_script_path, _pending_future

    with _pending_lock:
        if _pending_future is not None and not _pending_future.done():
            _pending_future.set_exception(
                RuntimeError("Diagnostic cleared before execution")
            )
        _pending_script_path = None
        _pending_future = None


# =============================================================================
# PFC Callback Function (Executed in main thread during cycle gaps)
# =============================================================================

def _pfc_diagnostic_callback():
    # type: () -> None
    """
    PFC callback - Execute pending diagnostic script.

    This function is called by PFC after each cycle. It checks if there's
    a pending diagnostic script and executes it.

    No parameters - reads from global _pending_script_path.

    Note:
        - Must be fast when no diagnostic pending (just a None check)
        - Script execution happens in PFC main thread
        - Result returned via Future.set_result()
    """
    global _pending_script_path, _pending_future

    # Fast path: no pending diagnostic (99% of the time)
    if _pending_script_path is None:
        return

    # Take ownership of pending diagnostic
    with _pending_lock:
        if _pending_script_path is None or _pending_future is None:
            return

        script_path = _pending_script_path
        future = _pending_future
        _pending_script_path = None
        _pending_future = None

    logger.info("Executing diagnostic via callback: {}".format(script_path))

    # Execute script
    try:
        import itasca  # type: ignore

        # Read script content
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()

        # Execute in isolated namespace with itasca available
        exec_context = {"itasca": itasca}
        exec(script_content, exec_context, exec_context)

        # Get result if script defined 'result' variable
        result = exec_context.get("result", None)

        future.set_result({
            "status": "success",
            "message": "Diagnostic executed via callback",
            "data": result
        })

        logger.info("Diagnostic completed via callback: {}".format(script_path))

    except Exception as e:
        logger.error("Diagnostic callback execution failed: {}".format(e))
        future.set_exception(e)


# =============================================================================
# Callback Registration
# =============================================================================

_callback_registered = False


def register_diagnostic_callback(itasca_module, position=51.0):
    # type: (Any, float) -> bool
    """
    Register diagnostic callback with PFC.

    Must be called once during server startup. This function:
    1. Injects _pfc_diagnostic_callback into __main__ namespace
    2. Registers callback with itasca.set_callback()

    Args:
        itasca_module: The itasca module (imported in PFC environment)
        position: Cycle execution position (default: 51.0)
            - 50.0: interrupt check callback
            - 51.0: diagnostic execution (after interrupt)

    Returns:
        bool: True if registered successfully, False if already registered
    """
    global _callback_registered

    if _callback_registered:
        logger.warning("Diagnostic callback already registered")
        return False

    try:
        # Inject function into __main__ namespace (required for PFC lookup)
        import __main__
        __main__._pfc_diagnostic_callback = _pfc_diagnostic_callback # type: ignore

        # Register with PFC
        itasca_module.set_callback("_pfc_diagnostic_callback", position)

        _callback_registered = True
        logger.info("Diagnostic callback registered (position: {})".format(position))
        return True

    except Exception as e:
        logger.error("Failed to register diagnostic callback: {}".format(e))
        return False


def unregister_diagnostic_callback(itasca_module, position=51.0):
    # type: (Any, float) -> bool
    """
    Unregister diagnostic callback from PFC.

    Args:
        itasca_module: The itasca module
        position: Same position used in registration

    Returns:
        bool: True if unregistered successfully
    """
    global _callback_registered

    if not _callback_registered:
        return False

    try:
        itasca_module.remove_callback("_pfc_diagnostic_callback", position)
        _callback_registered = False
        logger.info("Diagnostic callback unregistered")
        return True

    except Exception as e:
        logger.error("Failed to unregister diagnostic callback: {}".format(e))
        return False


def is_callback_registered():
    # type: () -> bool
    """Check if diagnostic callback is registered."""
    return _callback_registered
