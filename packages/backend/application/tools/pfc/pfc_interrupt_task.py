"""
PFC Interrupt Task Tool - MCP tool for interrupting running PFC tasks.

Provides the ability to stop long-running PFC simulations gracefully.
"""

from backend.application.tools.registrar import ToolRegistrar
from fastmcp.server.context import Context
from typing import Dict, Any
from backend.infrastructure.pfc import get_pfc_client
from backend.shared.utils.tool_result import success_response, error_response
from .utils import TaskId


def register_pfc_interrupt_task_tool(registrar: ToolRegistrar):
    """
    Register PFC interrupt task tool with the registrar.

    Args:
        registrar: Tool registrar instance
    """

    @registrar.tool(
        tags={"pfc", "task", "interrupt", "control"},
        annotations={"category": "pfc", "tags": ["pfc", "task", "interrupt"]}
    )
    async def pfc_interrupt_task(
        context: Context,
        task_id: TaskId,
    ) -> Dict[str, Any]:
        """
        Request interrupt for a running PFC task.

        Sends an interrupt signal to stop a long-running simulation gracefully.
        The task will be interrupted at the end of the current cycle.

        After calling this, use pfc_check_task_status to verify the task
        was actually interrupted (status will change to "interrupted").
        """
        try:
            # Parameter is pre-validated by Pydantic Annotated type

            # Get WebSocket client (auto-connects if needed)
            client = await get_pfc_client()

            # Send interrupt request
            result = await client.interrupt_task(task_id)

            status = result.get("status")

            if status == "success":
                llm_text = (
                    f"task_id: {task_id}\n"
                    f"interrupt signal sent\n\n"
                    f"Next: use pfc_check_task_status to verify"
                )

                return success_response(
                    message=f"Interrupt requested for task: {task_id}",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    task_id=task_id,
                    interrupt_requested=True
                )

            else:
                error_msg = result.get("message", "Unknown error")
                return error_response(
                    message=f"Failed to interrupt task: {error_msg}",
                    task_id=task_id
                )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error requesting interrupt: {str(e)}")
