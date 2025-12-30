"""
Utility message handlers.

Handles ping/pong heartbeat and task interruption.
"""

from datetime import datetime
from typing import Any, Dict

from .context import ServerContext


async def handle_ping(ctx, data):
    # type: (ServerContext, Dict[str, Any]) -> Dict[str, Any]
    """
    Handle ping heartbeat message.

    Args:
        ctx: Server context (unused, for interface consistency)
        data: Message data (unused, for interface consistency)

    Returns:
        Response dict with pong and timestamp
    """
    _ = ctx, data  # Unused, but required for consistent handler interface
    return {
        "type": "pong",
        "timestamp": datetime.now().isoformat()
    }


async def handle_interrupt_task(ctx, data):
    # type: (ServerContext, Dict[str, Any]) -> Dict[str, Any]
    """
    Handle interrupt_task message - request interrupt for a running task.

    Args:
        ctx: Server context with dependencies
        data: Message data containing:
            - request_id: Request identifier
            - task_id: Task ID to interrupt

    Returns:
        Response dict with interrupt request result
    """
    from ..managers import request_interrupt

    request_id = data.get("request_id", "unknown")
    task_id = data.get("task_id", "")

    if not task_id:
        return {
            "type": "result",
            "request_id": request_id,
            "status": "error",
            "message": "task_id is required",
            "data": None
        }

    # Request interrupt (will be checked by PFC callback)
    success = request_interrupt(task_id)
    if success:
        return {
            "type": "result",
            "request_id": request_id,
            "status": "success",
            "message": "Interrupt requested for task: {}".format(task_id),
            "data": {"task_id": task_id, "interrupt_requested": True}
        }
    else:
        return {
            "type": "result",
            "request_id": request_id,
            "status": "error",
            "message": "Failed to request interrupt",
            "data": None
        }
