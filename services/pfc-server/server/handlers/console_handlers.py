"""
Console-related message handlers.

Handles quick Python execution and diagnostic script execution.
"""

import logging
from io import StringIO
from typing import Any, Dict

from .context import ServerContext
from .helpers import truncate_message

logger = logging.getLogger("PFC-Server")


async def handle_quick_python(ctx, data):
    # type: (ServerContext, Dict[str, Any]) -> Dict[str, Any]
    """
    Handle quick_python message - execute quick Python code from user console.

    Args:
        ctx: Server context with dependencies
        data: Message data containing:
            - request_id: Request identifier
            - session_id: Session identifier (default: "default")
            - workspace_path: Absolute path to workspace
            - code: Python code to execute
            - timeout_ms: Timeout in milliseconds (default: 30000)

    Returns:
        Response dict with execution result
    """
    request_id = data.get("request_id", "unknown")
    session_id = data.get("session_id", "default")
    workspace_path = data.get("workspace_path", "")
    code = data.get("code", "")
    timeout_ms = data.get("timeout_ms", 30000)

    try:
        # Validate required parameters
        if not workspace_path:
            raise ValueError("workspace_path is required")
        if not code or not code.strip():
            raise ValueError("code cannot be empty")

        # Get or create QuickConsoleManager for this workspace
        console_manager = ctx.get_quick_console_manager(workspace_path)

        # Create temporary script file
        code_preview = console_manager.get_code_preview(code)
        script_name, script_path, _ = console_manager.create_script(
            code,
            description=code_preview
        )

        # Execute using existing script executor (synchronous for quick commands)
        result = await ctx.script_executor.execute_script(
            session_id=session_id,
            script_path=script_path,
            description=code_preview,
            timeout_ms=timeout_ms,
            run_in_background=False,
            source="user_console",
            enable_git_snapshot=False
        )

        # Add code preview to response data
        if result.get("data"):
            result["data"]["code_preview"] = code_preview

        # Truncate message before sending
        if "message" in result:
            result["message"] = truncate_message(result["message"])

        return {
            "type": "quick_python_result",
            "request_id": request_id,
            **result
        }

    except ValueError as e:
        return {
            "type": "quick_python_result",
            "request_id": request_id,
            "status": "error",
            "message": str(e),
            "data": None
        }
    except Exception as e:
        logger.error(f"Quick Python execution failed: {e}")
        return {
            "type": "quick_python_result",
            "request_id": request_id,
            "status": "error",
            "message": f"Execution failed: {e}",
            "data": None
        }


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

        import concurrent.futures
        import os
        import uuid

        # Read script content
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()

        # Generate task_id for tracking
        # Use StringIO for diagnostic scripts (quick, no persistence needed)
        task_id = uuid.uuid4().hex[:8]
        output_buffer = StringIO()

        # Strategy 1: Try queue execution with short timeout (1 second)
        queue_future = ctx.main_executor.submit(
            ctx.script_executor._execute_script_sync,
            script_path,
            script_content,
            output_buffer,
            task_id
        )

        try:
            # Wait 1 second for queue execution
            result = queue_future.result(timeout=1.0)
            logger.info("Diagnostic executed via queue: {}".format(
                os.path.basename(script_path)
            ))
            return {
                "type": "diagnostic_result",
                "request_id": request_id,
                "execution_path": "queue",
                **result
            }

        except concurrent.futures.TimeoutError:
            # Queue execution timed out (queue blocked)
            # Strategy 2: Use callback execution (works during cycle)
            logger.info("Queue blocked, switching to callback execution")

            from ..diagnostic_executor import submit_diagnostic, is_callback_registered

            if not is_callback_registered():
                raise RuntimeError(
                    "Diagnostic callback not registered and queue is blocked. "
                    "Restart PFC server to enable callback execution."
                )

            # Submit to callback executor
            callback_future = submit_diagnostic(script_path)

            # Wait for callback execution
            timeout_sec = (timeout_ms - 1000) / 1000.0
            timeout_sec = max(timeout_sec, 1.0)

            try:
                result = callback_future.result(timeout=timeout_sec)
                logger.info("Diagnostic executed via callback: {}".format(
                    os.path.basename(script_path)
                ))
                return {
                    "type": "diagnostic_result",
                    "request_id": request_id,
                    "execution_path": "callback",
                    **result
                }
            except concurrent.futures.TimeoutError:
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
