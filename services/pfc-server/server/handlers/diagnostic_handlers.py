"""
Diagnostic message handlers.

Handles diagnostic script execution for agent tools (e.g., pfc_capture_plot).
"""

import asyncio
import concurrent.futures
import logging
import os
from io import StringIO
from typing import Any, Dict, Optional, Tuple

from .context import ServerContext
from .helpers import require_field

logger = logging.getLogger("PFC-Server")


async def _wait_for_file(
    result: Dict[str, Any],
    max_wait_seconds: float = 30.0,
    poll_interval: float = 0.2
) -> Dict[str, Any]:
    """
    Wait for export file to exist.

    This function runs asynchronously without blocking PFC main thread.
    No delete needed - plot create auto-clears items on next capture.

    Args:
        result: Diagnostic script result containing data.output_path
        max_wait_seconds: Maximum time to wait for file
        poll_interval: Time between file existence checks

    Returns:
        Updated result dict with file verification status
    """
    # Extract output path from result
    data = result.get("data")
    if not isinstance(data, dict):
        return result

    output_path = data.get("output_path")

    if not output_path:
        return result

    # Async wait for file to exist (non-blocking)
    elapsed = 0.0
    while not os.path.exists(output_path) and elapsed < max_wait_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    if not os.path.exists(output_path):
        logger.error("Export file not created after {}s: {}".format(max_wait_seconds, output_path))
        return {
            **result,
            "status": "error",
            "message": "Export timeout: file not created after {}s".format(max_wait_seconds)
        }

    logger.info("Export file verified: {}".format(os.path.basename(output_path)))

    return result


async def _await_future_with_timeout(
    loop: asyncio.AbstractEventLoop,
    future: concurrent.futures.Future,
    timeout: float
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Await a concurrent.futures.Future with timeout, non-blocking.

    Args:
        loop: Event loop for run_in_executor
        future: Future to await
        timeout: Timeout in seconds

    Returns:
        Tuple of (result, timed_out):
            - (result_dict, False) if completed within timeout
            - (None, True) if timed out
    """
    try:
        result = await loop.run_in_executor(None, future.result, timeout)
        return result, False
    except concurrent.futures.TimeoutError:
        return None, True


async def handle_diagnostic_execute(ctx, data):
    # type: (ServerContext, Dict[str, Any]) -> Dict[str, Any]
    """
    Handle diagnostic_execute message - execute diagnostic script with smart path selection.

    Execution strategy:
    1. Try queue execution first (1s timeout) - works when PFC is idle
    2. If queue blocked, use callback execution - works during cycle

    Timeout budget:
    - Total timeout: timeout_ms (default 30000ms)
    - Queue wait: 1s (plot commands execute quickly)
    - Script execution: variable
    - File wait: remaining time after script execution

    Args:
        ctx: Server context with dependencies
        data: Message data containing:
            - request_id: Request identifier
            - script_path: Path to diagnostic script
            - timeout_ms: Timeout in milliseconds (default: 30000)

    Returns:
        Response dict with diagnostic result
    """
    import time as time_module

    request_id = data.get("request_id", "unknown")

    script_path, err = require_field(data, "script_path", request_id, "diagnostic_result")
    if err:
        return err

    timeout_ms = data.get("timeout_ms", 30000)

    # Track start time for timeout budget
    start_time = time_module.time()
    total_timeout_sec = timeout_ms / 1000.0

    def remaining_time():
        """Calculate remaining time in seconds."""
        elapsed = time_module.time() - start_time
        return max(total_timeout_sec - elapsed, 0.5)  # At least 0.5s

    try:

        import os
        import uuid

        # Read script content
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()

        # Generate task_id for tracking
        # Use StringIO for diagnostic scripts (quick, no persistence needed)
        task_id = uuid.uuid4().hex[:8]
        output_buffer = StringIO()

        # Get event loop for non-blocking waits
        loop = asyncio.get_event_loop()

        # Strategy 1: Try queue execution with 1 second timeout
        # Plot commands execute quickly (~1s), so short timeout is sufficient
        # If timeout, likely blocked by long-running cycle
        queue_timeout = min(1.0, remaining_time())
        queue_future = ctx.main_executor.submit(
            ctx.script_runner._execute,
            script_path,
            script_content,
            output_buffer,
            task_id
        )

        result, queue_blocked = await _await_future_with_timeout(loop, queue_future, queue_timeout)

        if not queue_blocked and result is not None:
            # Queue was available, execution completed
            logger.info("Diagnostic executed via queue: {}".format(
                os.path.basename(script_path)
            ))
            # Wait for export file with remaining time budget
            file_wait_timeout = remaining_time()
            result = await _wait_for_file(result, max_wait_seconds=file_wait_timeout)
            return {
                "type": "diagnostic_result",
                "request_id": request_id,
                "execution_path": "queue",
                **result
            }

        # Queue timed out - try to cancel the queued task to prevent double execution
        # cancel() returns True if task was successfully cancelled (not yet started)
        # Returns False if task is already running or completed
        cancelled = queue_future.cancel()
        if cancelled:
            logger.info("Queue blocked, cancelled queue task, switching to callback execution")
        else:
            # Task already started executing in queue - wait for it instead of double-submitting
            logger.info("Queue task already started, waiting for queue completion")
            try:
                # Wait for remaining time (half for execution, half for file wait)
                exec_timeout = remaining_time() * 0.5
                result = await loop.run_in_executor(None, queue_future.result, exec_timeout)
                # Wait for export file with remaining time budget
                file_wait_timeout = remaining_time()
                result = await _wait_for_file(result, max_wait_seconds=file_wait_timeout)
                return {
                    "type": "diagnostic_result",
                    "request_id": request_id,
                    "execution_path": "queue_delayed",
                    **result
                }
            except concurrent.futures.TimeoutError:
                return {
                    "type": "diagnostic_result",
                    "request_id": request_id,
                    "status": "timeout",
                    "message": "Diagnostic timed out after {}ms (queue delayed)".format(timeout_ms),
                    "data": None
                }

        # Strategy 2: Queue blocked and cancelled, use callback execution (works during cycle)
        logger.info("Queue blocked, switching to callback execution")

        from ..signals import submit_diagnostic, is_diagnostic_callback_registered as is_callback_registered

        if not is_callback_registered():
            raise RuntimeError(
                "Diagnostic callback not registered and queue is blocked. "
                "Restart PFC server to enable callback execution."
            )

        # Submit to callback executor
        callback_future = submit_diagnostic(script_path)

        # Wait for callback execution (half remaining time for execution, half for file wait)
        callback_timeout = remaining_time() * 0.5
        result, timed_out = await _await_future_with_timeout(loop, callback_future, callback_timeout)

        if not timed_out and result is not None:
            logger.info("Diagnostic executed via callback: {}".format(
                os.path.basename(script_path)
            ))
            # Wait for export file with remaining time budget
            file_wait_timeout = remaining_time()
            result = await _wait_for_file(result, max_wait_seconds=file_wait_timeout)
            return {
                "type": "diagnostic_result",
                "request_id": request_id,
                "execution_path": "callback",
                **result
            }

        # Both strategies failed
        return {
            "type": "diagnostic_result",
            "request_id": request_id,
            "status": "timeout",
            "message": "Diagnostic timed out after {}ms. "
                       "Queue blocked and no cycle running.".format(timeout_ms),
            "data": None
        }

    except ValueError as e:
        return {
            "type": "diagnostic_result",
            "request_id": request_id,
            "status": "error",
            "message": str(e),
            "data": None
        }
    except RuntimeError as e:
        return {
            "type": "diagnostic_result",
            "request_id": request_id,
            "status": "error",
            "message": str(e),
            "data": None
        }
    except Exception as e:
        logger.error(f"Diagnostic execution failed: {e}")
        return {
            "type": "diagnostic_result",
            "request_id": request_id,
            "status": "error",
            "message": f"Diagnostic execution failed: {e}",
            "data": None
        }
