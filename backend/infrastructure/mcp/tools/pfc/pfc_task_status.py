"""
PFC Task Status Tool - MCP tool for checking individual task status.

Provides real-time status monitoring and output retrieval for long-running PFC tasks.
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


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
            description=(
                "Task ID returned by pfc_execute_script tool when script was submitted. "
                "Example: 'a1b2c3d4'"
            )
        )
    ) -> Dict[str, Any]:
        """
        Check status and retrieve output of a long-running PFC script.

        Use this tool to monitor scripts submitted via pfc_execute_script.
        Returns real-time progress updates and captured print() output.

        Note:
            - Output shows print() statements from running script
            - Scripts continuously export data - read CSV/JSON/checkpoints anytime for analysis
            - Call multiple times to see progress updates
            - Task status available until server restart or cleanup
        """
        try:
            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Query task status
            result = await client.check_task_status(task_id)

            status = result.get("status")

            if status == "not_found":
                # Task not found - still a successful tool call
                return success_response(
                    message=f"Task not found: {task_id}",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"⚠ Task not found: {task_id}\n"
                                   "The task may have expired or the task ID is invalid."
                        }]
                    },
                    task_id=task_id,
                    task_status="not_found"
                )

            elif status == "running":
                # Task still running
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")

                return success_response(
                    message=result.get("message", f"Task running: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": (
                                f"⏳ Task is running: {task_id}\n"
                                f"Elapsed time: {elapsed_time:.2f}s\n"
                                f"Output so far:\n{output if output else '(no output yet)'}"
                            )
                        }]
                    },
                    task_id=task_id,
                    task_status="running",
                    task_data=data
                )

            elif status == "success":
                # Task completed successfully
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")
                task_result = data.get("result")

                return success_response(
                    message=result.get("message", f"Task completed: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": (
                                f"✓ Task completed successfully: {task_id}\n"
                                f"Elapsed time: {elapsed_time:.2f}s\n"
                                f"Result: {task_result}\n"
                                f"Output:\n{output if output else '(no output)'}"
                            )
                        }]
                    },
                    task_id=task_id,
                    task_status="success",
                    task_data=data
                )

            elif status == "error":
                # Task failed with error
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")
                error_msg = data.get("error", "Unknown error")

                return success_response(
                    message=result.get("message", f"Task failed: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": (
                                f"✗ Task failed: {task_id}\n"
                                f"Elapsed time: {elapsed_time:.2f}s\n"
                                f"Error: {error_msg}\n"
                                f"Output before error:\n{output if output else '(no output)'}"
                            )
                        }]
                    },
                    task_id=task_id,
                    task_status="error",
                    task_data=data
                )

            else:
                # Unknown status
                return success_response(
                    message=f"Unknown task status: {status}",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"⚠ Unknown task status: {status}"
                        }]
                    },
                    task_id=task_id,
                    task_status=status
                )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error querying task status: {str(e)}")

    print(f"[DEBUG] Registered PFC task status tool: pfc_check_task_status")
