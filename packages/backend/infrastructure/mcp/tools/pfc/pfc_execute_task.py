"""
PFC Task Execution Tool - MCP tool for executing PFC simulation tasks.

Provides task execution functionality for PFC Python SDK operations.
Each execution creates a versioned snapshot on the pfc-executions branch
for complete traceability ("Script is Context" philosophy).
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any, Optional
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators
from backend.infrastructure.pfc.task_status_formatter import (
    create_task_status_data,
    format_task_status_for_llm,
    DEFAULT_OUTPUT_LINES,
)


def register_pfc_task_tool(mcp: FastMCP):
    """
    Register PFC task execution tool with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        tags={"pfc", "simulation", "python", "task", "sdk"},
        annotations={"category": "pfc", "tags": ["pfc", "simulation", "python", "sdk"]}
    )
    async def pfc_execute_task(
        context: Context,
        entry_script: str = Field(
            ...,
            description="The absolute path to the entry script to execute"
        ),
        description: str = Field(
            ...,
            description=(
                "Brief description of what this task does (5-15 words). "
                "Examples: 'Compression test with 100kPa confining pressure', "
                "'Triaxial shear test under drained conditions'"
            )
        ),
        timeout: Optional[int] = Field(
            default=None,
            description=(
                "Timeout in milliseconds (None = no limit). "
                "Range: 1000-600000. Only applies when run_in_background=False. "
                "Recommended: 60000-120000ms for testing."
            )
        ),
        run_in_background: bool = Field(
            default=True,
            description=(
                "When true (default), returns task_id immediately without blocking. "
                "When false, waits for completion. "
                "Use pfc_check_task_status to monitor background tasks."
            )
        )
    ) -> Dict[str, Any]:
        """
        Execute a PFC simulation task.

        Returns task_id for tracking. Scripts can print progress during execution,
        monitor real-time output via pfc_check_task_status(task_id).

        Note: Query pfc_query_command for command syntax before writing scripts.
        """
        try:
            # Get session ID from MCP context for task isolation
            session_id = getattr(context, 'client_id', None) if context else None
            if not session_id:
                return error_response("Session ID not available")

            # Validate description length (LLM-friendly guidance)
            if not description or not description.strip():
                return error_response(
                    "description is required. Please provide a brief explanation of what this task does. "
                    "Example: 'Initial settling simulation with 10k particles'"
                )

            description = description.strip()
            if len(description) > 200:
                return error_response(
                    f"description is too long ({len(description)} characters). "
                    "Please keep it concise (recommended: 30-80 characters, max: 200). "
                    "Focus on the task's purpose rather than implementation details."
                )

            # Normalize path separators for cross-platform compatibility
            if not entry_script or not entry_script.strip():
                return error_response("entry_script is required and cannot be empty")
            script_path = normalize_path_separators(entry_script.strip(), target_platform='linux')

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute script (server handles git versioning)
            result = await client.execute_task(
                script_path=script_path,
                description=description,
                timeout_ms=timeout,
                run_in_background=run_in_background,
                session_id=session_id
            )

            # Handle result based on execution mode
            status = result.get("status")
            data = result.get("data")

            if run_in_background:
                # ===== Background Mode =====
                if status != "pending":
                    return error_response(
                        f"Unexpected server response in background mode: status={status} "
                        f"(expected 'pending'). Server may have changed behavior."
                    )

                # Use unified formatter for consistent output format
                task_id = data.get("task_id") if data else None

                # Create structured task data using shared formatter
                task_data = create_task_status_data(data or {}, task_id or "unknown")
                task_data.status = "submitted"  # Map "pending" to "submitted" for display
                task_data.description = description  # Use tool parameter

                # Format using unified formatter
                formatted = format_task_status_for_llm(
                    data=task_data,
                    offset=0,
                    limit=DEFAULT_OUTPUT_LINES,
                )

                return success_response(
                    message=result.get("message", f"Task submitted: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": formatted.text
                        }]
                    },
                    entry_script=script_path,
                    task_id=task_id,
                    git_commit=task_data.git_commit,
                    pagination=formatted.pagination
                )

            else:
                # ===== Foreground Mode (Synchronous) =====
                # Use unified formatter for consistent output format
                task_id = data.get("task_id") if data else None

                # Map status to display status (ensure status is str for type safety)
                status_str = str(status) if status else "unknown"
                status_map: dict[str, str] = {
                    "success": "completed",
                    "error": "failed",
                }
                display_status = status_map.get(status_str, status_str)

                # Create structured task data using shared formatter
                task_data = create_task_status_data(data or {}, task_id or "unknown")
                task_data.status = display_status
                task_data.description = description  # Use tool parameter, not server data

                # Ensure error is set (fallback to result.message if data.error is missing)
                if not task_data.error and status != "success":
                    task_data.error = result.get("message", "Task execution failed")

                # Format using unified formatter (consistent with pfc_check_task_status)
                formatted = format_task_status_for_llm(
                    data=task_data,
                    offset=0,
                    limit=DEFAULT_OUTPUT_LINES,
                )

                # Build response based on status
                if status == "success":
                    return success_response(
                        message=result.get("message", f"Task completed: {script_path}"),
                        llm_content={
                            "parts": [{
                                "type": "text",
                                "text": formatted.text
                            }]
                        },
                        entry_script=script_path,
                        task_id=task_id,
                        git_commit=task_data.git_commit,
                        script_result=task_data.result,
                        pagination=formatted.pagination
                    )
                else:
                    return success_response(
                        message=result.get("message", f"Task failed: {script_path}"),
                        llm_content={
                            "parts": [{
                                "type": "text",
                                "text": formatted.text
                            }]
                        },
                        entry_script=script_path,
                        task_id=task_id,
                        git_commit=task_data.git_commit,
                        script_error=task_data.error,
                        pagination=formatted.pagination
                    )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error executing task: {str(e)}")

    print(f"[DEBUG] Registered PFC task tool: pfc_execute_task")
