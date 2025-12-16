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
from backend.infrastructure.mcp.utils.pagination import format_paginated_output
from backend.infrastructure.mcp.utils.time_utils import format_time_range
import time


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

                # Extract metadata from unified data structure
                task_id = data.get("task_id") if data else None
                entry_script_display = data.get("entry_script", data.get("script_path", script_path)) if data else script_path
                submit_time = data.get("start_time", time.time()) if data else time.time()
                git_commit = data.get("git_commit") if data else None
                time_info = format_time_range(submit_time)

                # Build version info string
                version_info = f" | git_commit: {git_commit[:8]}" if git_commit else ""

                return success_response(
                    message=result.get("message", f"Task submitted: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": (
                                f"**STATUS**: Task submitted | task_id: {task_id} | {time_info}{version_info}\n"
                                f"  Entry: {entry_script_display}\n"
                                f"  → {description}\n\n"
                                f"Use pfc_check_task_status to monitor progress."
                            )
                        }]
                    },
                    entry_script=script_path,
                    git_commit=git_commit,
                    result=data
                )

            else:
                # ===== Foreground Mode (Synchronous) =====
                if status == "success":
                    # Task completed successfully
                    task_id = data.get("task_id") if data else None
                    entry_script_display = data.get("entry_script", data.get("script_path", script_path)) if data else script_path
                    output = data.get("output", "") if data else ""
                    script_result = data.get("result") if data else None
                    start_time = data.get("start_time") if data else None
                    end_time = data.get("end_time") if data else None
                    git_commit = data.get("git_commit") if data else None

                    # Use pagination utility to extract output summary
                    output_text, pagination = format_paginated_output(output, offset=0, limit=10)

                    # Build navigation hints
                    nav_hints = []
                    if pagination["has_earlier"]:
                        nav_hints.append(f"older: offset={10}")
                    nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                    # Build LLM-friendly text
                    llm_text_parts = []

                    # 1. Success message with version info
                    time_info = format_time_range(start_time, end_time)
                    version_info = f" | git_commit: {git_commit[:8]}" if git_commit else ""
                    llm_text_parts.append(
                        f"**STATUS**: Completed | task_id: {task_id} | {time_info}{version_info}\n"
                        f"  Entry: {entry_script_display}\n"
                        f"  → {description}"
                    )

                    # 2. Output summary
                    if output:
                        llm_text_parts.append(
                            f"\nOutput: {pagination['total_lines']} lines total | "
                            f"Showing: last {pagination['displayed_count']} lines\n\n"
                            f"━━━ Output Summary ━━━\n"
                            f"{output_text}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"**NEXT**: {nav_hint}"
                        )

                    # 3. Structured result
                    if script_result is not None:
                        llm_text_parts.append(f"\n\n=== Script Result ===\n{script_result}")

                    llm_text = "".join(llm_text_parts)

                    return success_response(
                        message=result.get("message", f"Task completed: {script_path}"),
                        llm_content={
                            "parts": [{
                                "type": "text",
                                "text": llm_text
                            }]
                        },
                        entry_script=script_path,
                        task_id=task_id,
                        git_commit=git_commit,
                        script_result=script_result,
                        pagination=pagination
                    )

                else:
                    # Task execution failed
                    task_id = data.get("task_id") if data else None
                    entry_script_display = data.get("entry_script", data.get("script_path", script_path)) if data else script_path
                    output = data.get("output", "") if data else ""
                    error_message = data.get("error", result.get("message", "Task execution failed")) if data else result.get("message", "Task execution failed")
                    start_time = data.get("start_time") if data else None
                    end_time = data.get("end_time") if data else None
                    git_commit = data.get("git_commit") if data else None

                    # Use pagination utility
                    output_text, pagination = format_paginated_output(output, offset=0, limit=10)

                    nav_hints = []
                    if pagination["has_earlier"]:
                        nav_hints.append(f"older: offset={10}")
                    nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                    llm_text_parts = []

                    # 1. Error message with version info
                    time_info = format_time_range(start_time, end_time)
                    version_info = f" | git_commit: {git_commit[:8]}" if git_commit else ""
                    llm_text_parts.append(
                        f"**STATUS**: Failed | task_id: {task_id} | {time_info}{version_info}\n"
                        f"  Entry: {entry_script_display}\n"
                        f"  → {description}\n\n"
                        f"Error: {error_message}"
                    )

                    # 2. Output before error
                    if output:
                        llm_text_parts.append(
                            f"\nOutput: {pagination['total_lines']} lines total | "
                            f"Showing: last {pagination['displayed_count']} lines\n\n"
                            f"━━━ Output before error ━━━\n"
                            f"{output_text}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"**NEXT**: {nav_hint}"
                        )

                    llm_text = "".join(llm_text_parts)

                    return success_response(
                        message=result.get("message", f"Task failed: {script_path}"),
                        llm_content={
                            "parts": [{
                                "type": "text",
                                "text": llm_text
                            }]
                        },
                        entry_script=script_path,
                        task_id=task_id,
                        git_commit=git_commit,
                        script_error=error_message,
                        pagination=pagination
                    )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error executing task: {str(e)}")

    print(f"[DEBUG] Registered PFC task tool: pfc_execute_task")
