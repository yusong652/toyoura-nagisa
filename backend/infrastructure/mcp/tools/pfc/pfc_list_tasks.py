"""
PFC List Tasks Tool - MCP tool for listing all tracked tasks.

Provides task overview functionality for managing multiple concurrent PFC simulations.
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


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
                task_lines = []
                for task in data:
                    task_id = task.get("task_id", "unknown")
                    name = task.get("name", "unknown")
                    status = task.get("status", "unknown")
                    elapsed = task.get("elapsed_time", 0)

                    status_icon = {
                        "running": "⏳",
                        "completed": "✓",
                        "failed": "✗"
                    }.get(status, "?")

                    task_lines.append(
                        f"{status_icon} {name} ({task_id}) - "
                        f"{status} - {elapsed:.2f}s"
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
