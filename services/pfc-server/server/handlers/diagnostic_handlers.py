"""
Diagnostic message handlers.

Handles diagnostic script execution for agent tools (e.g., pfc_capture_plot).
"""

import asyncio
import concurrent.futures
import logging
from io import StringIO
from typing import Any, Dict, Optional, Tuple

from .context import ServerContext

logger = logging.getLogger("PFC-Server")


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

    Args:
        ctx: Server context with dependencies
        data: Message data containing:
            - request_id: Request identifier
            - script_path: Path to diagnostic script
            - timeout_ms: Timeout in milliseconds (default: 30000)

    Returns:
        Response dict with diagnostic result
    """
    request_id = data.get("request_id", "unknown")
    script_path = data.get("script_path", "")
    timeout_ms = data.get("timeout_ms", 30000)

    try:
        if not script_path:
            raise ValueError("script_path is required")

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

        # Strategy 1: Try queue execution with short timeout (1 second)
        # This detects if the main thread queue is blocked by a long-running task
        queue_future = ctx.main_executor.submit(
            ctx.script_runner._execute,
            script_path,
            script_content,
            output_buffer,
            task_id
        )

        result, queue_blocked = await _await_future_with_timeout(loop, queue_future, 1.0)

        if not queue_blocked and result is not None:
            # Queue was available, execution completed
            logger.info("Diagnostic executed via queue: {}".format(
                os.path.basename(script_path)
            ))
            return {
                "type": "diagnostic_result",
                "request_id": request_id,
                "execution_path": "queue",
                **result
            }

        # Strategy 2: Queue blocked, use callback execution (works during cycle)
        logger.info("Queue blocked, switching to callback execution")

        from ..executors import submit_diagnostic, is_callback_registered

        if not is_callback_registered():
            raise RuntimeError(
                "Diagnostic callback not registered and queue is blocked. "
                "Restart PFC server to enable callback execution."
            )

        # Submit to callback executor
        callback_future = submit_diagnostic(script_path)

        # Wait for callback execution
        timeout_sec = max((timeout_ms - 1000) / 1000.0, 1.0)
        result, timed_out = await _await_future_with_timeout(loop, callback_future, timeout_sec)

        if not timed_out and result is not None:
            logger.info("Diagnostic executed via callback: {}".format(
                os.path.basename(script_path)
            ))
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
