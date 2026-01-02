"""
Console-related message handlers.

Handles user console Python execution (> prefix commands).
"""

import logging
from typing import Any, Dict

from .context import ServerContext
from .helpers import truncate_message

logger = logging.getLogger("PFC-Server")


async def handle_user_console(ctx, data):
    # type: (ServerContext, Dict[str, Any]) -> Dict[str, Any]
    """
    Handle user_console message - execute Python code from user console.

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
        # Get or create UserConsoleManager for this workspace
        console_manager = ctx.get_user_console_manager(workspace_path)

        # Create temporary script file
        code_preview = console_manager.get_code_preview(code)
        script_name, script_path, _ = console_manager.create_script(
            code,
            description=code_preview
        )

        # Execute using script runner (synchronous for quick commands)
        result = await ctx.script_runner.run(
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
            "type": "user_console_result",
            "request_id": request_id,
            **result
        }

    except Exception as e:
        logger.error(f"User console execution failed: {e}")
        return {
            "type": "user_console_result",
            "request_id": request_id,
            "status": "error",
            "message": f"Execution failed: {e}",
            "data": None
        }
