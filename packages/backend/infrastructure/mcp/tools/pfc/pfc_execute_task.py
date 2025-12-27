"""
PFC Task Execution Tool - MCP tool for executing PFC simulation tasks.

Provides task execution functionality for PFC Python SDK operations.
Each execution creates a versioned snapshot on the pfc-executions branch
for complete traceability ("Script is Context" philosophy).
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any, cast
from backend.infrastructure.pfc import get_pfc_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators
from .utils import (
    create_task_status_data,
    format_task_status_for_llm,
    DEFAULT_OUTPUT_LINES,
    ScriptPath,
    TaskDescription,
    TimeoutMs,
    RunInBackground,
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
        entry_script: ScriptPath,
        description: TaskDescription,
        timeout: TimeoutMs = None,
        run_in_background: RunInBackground = True,
    ) -> Dict[str, Any]:
        """
        Execute a PFC simulation task.

        Returns task_id for tracking. Scripts can print progress during execution,
        monitor real-time output via pfc_check_task_status(task_id).

        Note: Query pfc_query_command for command syntax before writing scripts.
        """
        try:
            # Get session ID from MCP context for task isolation
            # Architecture guarantee: tool_manager.py always injects _meta.client_id
            session_id = cast(str, context.client_id)

            # Parameters are pre-validated by Pydantic Annotated types
            # Normalize path separators for cross-platform compatibility
            script_path = normalize_path_separators(entry_script, target_platform='linux')

            # Get WebSocket client (auto-connects if needed)
            client = await get_pfc_client()

            # Execute script (server handles git versioning)
            result = await client.execute_task(
                script_path=script_path,
                description=description,
                timeout_ms=timeout,
                run_in_background=run_in_background,
                session_id=session_id
            )

            # Validate background mode response
            status = result.get("status")
            data = result.get("data")

            if run_in_background and status != "pending":
                return error_response(
                    f"Unexpected server response in background mode: status={status} "
                    f"(expected 'pending'). Server may have changed behavior."
                )

            # ===== Unified Response Building =====
            # Status mapping: server status → display status
            # - pending (background or foreground timeout): submitted/running
            # - success/error/interrupted (foreground completed): completed/failed/interrupted
            STATUS_MAP: dict[str, str] = {
                "pending": "submitted" if run_in_background else "running",
                "success": "completed",
                "error": "failed",
            }
            display_status = STATUS_MAP.get(str(status), str(status))

            # Create structured task data
            task_id = data.get("task_id") if data else None
            task_data = create_task_status_data(data or {}, task_id or "unknown")
            task_data.status = display_status
            task_data.description = description

            # Set error message for failed tasks
            if status == "error" and not task_data.error:
                task_data.error = result.get("message", "Task execution failed")

            # Format using unified formatter
            formatted = format_task_status_for_llm(
                data=task_data,
                offset=0,
                limit=DEFAULT_OUTPUT_LINES,
            )

            # Build response
            response_kwargs: Dict[str, Any] = {
                "message": result.get("message", f"Task {display_status}: {script_path}"),
                "llm_content": {"parts": [{"type": "text", "text": formatted.text}]},
                "entry_script": script_path,
                "task_id": task_id,
                "git_commit": task_data.git_commit,
                "pagination": formatted.pagination,
            }

            # Add status-specific fields for completed foreground tasks
            if status == "success":
                response_kwargs["script_result"] = task_data.result
            elif status == "error":
                response_kwargs["script_error"] = task_data.error

            return success_response(**response_kwargs)

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error executing task: {str(e)}")

    print(f"[DEBUG] Registered PFC task tool: pfc_execute_task")