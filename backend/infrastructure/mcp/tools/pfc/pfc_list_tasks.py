"""
PFC List Tasks Tool - MCP tool for listing all tracked tasks.

Provides task overview functionality for managing multiple concurrent PFC simulations.
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.time_utils import format_time_range


def register_pfc_list_tasks_tool(mcp: FastMCP):
    """
    Register PFC list tasks tool with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        tags={"pfc", "task", "list", "monitoring"},
        annotations={"category": "pfc", "tags": ["pfc", "task", "monitoring"]}
    )
    async def pfc_list_tasks(
        context: Context
    ) -> Dict[str, Any]:
        """
        List all tracked long-running PFC scripts.

        Returns overview of all script tasks (running, completed, failed) currently
        tracked by the PFC server. Useful for managing multiple concurrent simulations.

        Note:
            - Shows scripts submitted via pfc_execute_script
            - Task list persists until server restart
            - Use pfc_check_task_status for detailed output of specific scripts
        """
        try:
            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Query task list
            result = await client.list_tasks()

            data = result.get("data", [])
            task_count = len(data)

            # Format task summary for LLM
            if task_count == 0:
                task_summary = "No tasks currently tracked."
            else:
                # Sort tasks by start_time (newest first)
                sorted_data = sorted(data, key=lambda t: t.get("start_time", 0), reverse=True)

                task_lines = []
                for task in sorted_data:
                    task_id = task.get("task_id", "unknown")
                    script_path = task.get("script_path", task.get("name", "unknown"))  # Use script_path, fallback to name
                    description = task.get("description", "")  # Agent-provided description
                    status = task.get("status", "unknown")
                    elapsed = task.get("elapsed_time", 0)
                    start_time = task.get("start_time")
                    end_time = task.get("end_time")

                    status_icon = {
                        "running": "⏳",
                        "completed": "✓",
                        "failed": "✗"
                    }.get(status, "?")

                    # Format time info with date (important for long-running PFC workflows)
                    time_info = format_time_range(start_time, end_time)

                    task_lines.append(
                        f"{status_icon} Task ID: {task_id} | {elapsed:.1f}s | {time_info}\n"
                        f"  Script: {script_path}\n"
                        f"  → {description}"
                    )

                task_summary = (
                    f"Found {task_count} task{'s' if task_count > 1 else ''}:\n" +
                    "\n".join(task_lines)
                )

            return success_response(
                message=result.get("message", f"Listed {task_count} tasks"),
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": task_summary
                    }]
                },
                task_count=task_count,
                tasks=data
            )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error listing tasks: {str(e)}")

    print(f"[DEBUG] Registered PFC list tasks tool: pfc_list_tasks")
