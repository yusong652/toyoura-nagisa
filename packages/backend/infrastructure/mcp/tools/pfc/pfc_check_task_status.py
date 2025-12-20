"""
PFC Task Status Tool - MCP tool for checking individual task status.

Provides real-time status monitoring and output retrieval for long-running PFC tasks.
Uses shared task_status_formatter for consistent output format.
"""

import asyncio
from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any, Optional
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.pfc.task_status_formatter import (
    create_task_status_data,
    format_task_status_for_llm,
    DEFAULT_OUTPUT_LINES,
    MAX_OUTPUT_LINES,
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
        task_id: str = Field(
            ...,
            description="Task ID from pfc_execute_task (e.g., 'a1b2c3d4')"
        ),
        offset: int = Field(
            0,
            ge=0,
            description="Skip N newest lines (0=most recent, 10=skip 10 newest)"
        ),
        limit: int = Field(
            DEFAULT_OUTPUT_LINES,
            ge=1,
            le=MAX_OUTPUT_LINES,
            description=f"Lines to display (default: {DEFAULT_OUTPUT_LINES}, max: {MAX_OUTPUT_LINES})"
        ),
        filter: Optional[str] = Field(
            None,
            description="Optional text filter - only show lines containing this text (case-sensitive)"
        ),
        wait_seconds: float = Field(
            1,
            ge=1,
            le=3600,
            description="Wait N seconds before checking status (0-3600s). Use to avoid frequent polling. Example: wait_seconds=30 for long simulations"
        )
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
