"""
PFC Task Status Tool - MCP tool for checking individual task status.

Provides real-time status monitoring and output retrieval for long-running PFC tasks.
Uses shared task_status_formatter for consistent output format.
"""

import asyncio
from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.pfc.task_status_formatter import (
    create_task_status_data,
    format_task_status_for_llm,
)
from .models import (
    TaskId,
    OutputOffset,
    OutputLimit,
    FilterText,
    WaitSeconds,
)


def register_pfc_task_status_tool(mcp: FastMCP):
    """
    Register PFC task status tool with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        tags={"pfc", "task", "status", "monitoring"},
        annotations={"category": "pfc", "tags": ["pfc", "task", "monitoring"]}
    )
    async def pfc_check_task_status(
        context: Context,
        task_id: TaskId,
        offset: OutputOffset = 0,
        limit: OutputLimit = 20,
        filter: FilterText = None,
        wait_seconds: WaitSeconds = 1,
    ) -> Dict[str, Any]:
        """
        Check script status and retrieve output - works for both running and completed tasks.

        Monitor live progress with real-time print() output, or retrieve full output
        from scripts executed earlier (even after running other tasks).

        Pagination helps manage long outputs efficiently. All scripts (foreground/background)
        are tracked and persisted. Use pfc_list_tasks to find task IDs.

        Optional filtering allows focusing on specific output (e.g., errors, warnings).

        Rate limiting: Use wait_seconds to avoid frequent polling (e.g., wait_seconds=30
        waits 30s before checking, useful for long simulations).
        """
        try:
            # Wait before checking (rate limiting for long-running tasks)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Query task status
            result = await client.check_task_status(task_id)

            status = result.get("status", "unknown")

            if status == "not_found":
                # Task not found - still a successful tool call
                return success_response(
                    message=f"Task not found: {task_id}",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": (
                                f"**WARNING**: Task not found: {task_id}\n\n"
                                "The task may have expired or the task ID is invalid."
                            )
                        }]
                    },
                    task_id=task_id,
                    task_status="not_found"
                )

            # Map pfc-server status to display status
            status_map: dict[str, str] = {
                "running": "running",
                "success": "completed",
                "error": "failed",
                "interrupted": "interrupted",
            }
            display_status = status_map.get(status) or status

            # Extract data and create structured TaskStatusData
            data = result.get("data", {})
            task_data = create_task_status_data(data, task_id)
            task_data.status = display_status

            # Format using shared formatter
            formatted = format_task_status_for_llm(
                data=task_data,
                offset=offset,
                limit=limit,
                filter_text=filter,
            )

            return success_response(
                message=result.get("message", f"Task {display_status}: {task_id}"),
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": formatted.text
                    }]
                },
                task_id=task_id,
                task_status=status,  # Original status for data consistency
                task_data=data,
                pagination=formatted.pagination
            )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error querying task status: {str(e)}")

    print(f"[DEBUG] Registered PFC task status tool: pfc_check_task_status")
