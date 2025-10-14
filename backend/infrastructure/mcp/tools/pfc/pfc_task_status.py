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
from backend.infrastructure.mcp.utils.pagination import format_paginated_output


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
        ),
        offset: int = Field(
            0,
            ge=0,
            description=(
                "Line offset from the most recent output. "
                "0 = show most recent lines, 10 = skip 10 newest lines and show older ones. "
                "Use this to paginate through task output efficiently."
            )
        ),
        limit: int = Field(
            10,
            ge=1,
            le=100,
            description=(
                "Number of output lines to display. "
                "Default: 10 lines, Maximum: 100 lines. "
                "Helps conserve context window for long-running tasks."
            )
        )
    ) -> Dict[str, Any]:
        """
        Check status and retrieve output of a long-running PFC script.

        Use this tool to monitor scripts submitted via pfc_execute_script.
        Returns real-time progress updates and captured print() output.

        Pagination:
            - offset=0, limit=10: Show most recent 10 lines (default)
            - offset=10, limit=10: Skip 10 newest lines, show next 10 older lines
            - Navigate through output using offset parameter to conserve context
            - Total line count provided to help you plan pagination

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

                # Format paginated output
                output_text, pagination = format_paginated_output(output, offset, limit)

                # Build navigation hints
                nav_hints = []
                if pagination["has_later"]:
                    nav_hints.append(f"newer: offset={max(0, offset - limit)}")
                if pagination["has_earlier"]:
                    nav_hints.append(f"older: offset={offset + limit}")
                nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                # Build LLM-friendly text
                llm_text = (
                    f"⏳ Task running: {task_id} | Elapsed: {elapsed_time:.2f}s\n"
                    f"📊 Output: {pagination['total_lines']} lines total | "
                    f"Showing: lines {pagination['line_range']} "
                    f"({'most recent' if offset == 0 else f'offset {offset}'})\n\n"
                    f"━━━ Output ━━━\n"
                    f"{output_text}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💡 Navigate: {nav_hint}"
                )

                return success_response(
                    message=result.get("message", f"Task running: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    task_id=task_id,
                    task_status="running",
                    task_data=data,
                    pagination=pagination
                )

            elif status == "success":
                # Task completed successfully
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")
                task_result = data.get("result")

                # Format paginated output
                output_text, pagination = format_paginated_output(output, offset, limit)

                # Build navigation hints
                nav_hints = []
                if pagination["has_later"]:
                    nav_hints.append(f"newer: offset={max(0, offset - limit)}")
                if pagination["has_earlier"]:
                    nav_hints.append(f"older: offset={offset + limit}")
                nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                # Build LLM-friendly text
                llm_text = (
                    f"✓ Task completed: {task_id} | Elapsed: {elapsed_time:.2f}s\n"
                    f"Result: {task_result}\n"
                    f"📊 Output: {pagination['total_lines']} lines total | "
                    f"Showing: lines {pagination['line_range']} "
                    f"({'most recent' if offset == 0 else f'offset {offset}'})\n\n"
                    f"━━━ Output ━━━\n"
                    f"{output_text}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💡 Navigate: {nav_hint}"
                )

                return success_response(
                    message=result.get("message", f"Task completed: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    task_id=task_id,
                    task_status="success",
                    task_data=data,
                    pagination=pagination
                )

            elif status == "error":
                # Task failed with error
                data = result.get("data", {})
                elapsed_time = data.get("elapsed_time", 0)
                output = data.get("output", "")
                error_msg = data.get("error", "Unknown error")

                # Format paginated output
                output_text, pagination = format_paginated_output(output, offset, limit)

                # Build navigation hints
                nav_hints = []
                if pagination["has_later"]:
                    nav_hints.append(f"newer: offset={max(0, offset - limit)}")
                if pagination["has_earlier"]:
                    nav_hints.append(f"older: offset={offset + limit}")
                nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                # Build LLM-friendly text
                llm_text = (
                    f"✗ Task failed: {task_id} | Elapsed: {elapsed_time:.2f}s\n"
                    f"Error: {error_msg}\n"
                    f"📊 Output: {pagination['total_lines']} lines total | "
                    f"Showing: lines {pagination['line_range']} "
                    f"({'most recent' if offset == 0 else f'offset {offset}'})\n\n"
                    f"━━━ Output before error ━━━\n"
                    f"{output_text}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 Navigate: {nav_hint}"
                )

                return success_response(
                    message=result.get("message", f"Task failed: {task_id}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    task_id=task_id,
                    task_status="error",
                    task_data=data,
                    pagination=pagination
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
