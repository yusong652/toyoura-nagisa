"""
PFC Script Tools - MCP tool for executing Python SDK scripts.

Provides script execution functionality for PFC Python SDK operations
that return data (unlike native commands which don't return values).
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any, Optional
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators
from backend.infrastructure.mcp.utils.pagination import format_paginated_output
from backend.infrastructure.mcp.utils.time_utils import format_timestamp, format_time_range
import time


def register_pfc_script_tool(mcp: FastMCP):
    """
    Register PFC script tool with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        tags={"pfc", "simulation", "python", "script", "sdk"},
        annotations={"category": "pfc", "tags": ["pfc", "simulation", "python", "sdk"]}
    )
    async def pfc_execute_script(
        context: Context,
        script_path: str = Field(
            ...,
            description=(
                "Absolute path to Python script file for PFC SDK execution. "
                "Example: '/workspace/scripts/settling_sim.py'. "
                "Read the script first to understand its functionality."
            )
        ),
        timeout: Optional[int] = Field(
            default=None,
            description=(
                "Script execution timeout in milliseconds (None = no limit). Valid range: 1000-600000 (1s to 10min). "
                "Only applies when run_in_background=False. "
                "Recommended: 60000-120000ms for testing, None for production simulations."
            )
        ),
        run_in_background: bool = Field(
            default=True,
            description=(
                "Set to false to wait for completion and return result directly (for quick test scripts). "
                "When true, returns task_id immediately for long-running simulations. "
                "Query progress with pfc_check_task_status when using background mode."
            )
        )
    ) -> Dict[str, Any]:
        """
        Execute Python SDK script for long-running simulations and analysis.

        Data flow pattern (three channels):
            1. Real-time monitoring: Scripts print progress; check output via pfc_check_task_status
            2. Checkpoint persistence: Scripts save complete state with "model save"
            3. Analysis data: Scripts export CSV/JSON; write analysis scripts to process (don't read CSV directly)

        Usage workflow:
            1. Read script file to understand what it does
            2. Call this tool with script path → returns task_id
            3. Monitor progress with pfc_check_task_status (see print output)
            4. After completion, process exported files

        Note:
            For simple commands, use pfc_execute_command instead.
        """
        try:
            # Normalize path separators for cross-platform compatibility
            # This handles cases where LLM generates mixed separators (e.g., C:\path/to/file.py)
            # Note: PFC server expects forward slashes, so we normalize to Linux-style paths
            if not script_path or not script_path.strip():
                return error_response("script_path is required and cannot be empty")
            script_path = normalize_path_separators(script_path.strip(), target_platform='linux')

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute script
            # WebSocket timeout is auto-calculated based on timeout + infrastructure buffer
            result = await client.send_script(
                script_path=script_path,
                timeout_ms=timeout,
                run_in_background=run_in_background
            )

            # Handle result based on execution mode
            # Use run_in_background as primary branch logic (clearer intent)
            status = result.get("status")
            data = result.get("data")

            if run_in_background:
                # ===== Background Mode =====
                # Expect: status == "pending" (task submitted)
                # Return: task_id for progress monitoring
                if status != "pending":
                    # Protocol violation: background mode should return "pending"
                    return error_response(
                        f"Unexpected server response in background mode: status={status} "
                        f"(expected 'pending'). Server may have changed behavior."
                    )

                task_id = data.get("task_id") if data else None
                script_name = data.get("script_name") if data else "script"
                submit_time = time.time()
                time_info = format_time_range(submit_time)

                return success_response(
                    message=result.get("message", f"Script submitted: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"⏳ Task submitted: {script_name} | {time_info}\nTask ID: {task_id}\n\nUse pfc_check_task_status to monitor progress."
                        }]
                    },
                    script_path=script_path,
                    result=data
                )

            else:
                # ===== Foreground Mode (Synchronous) =====
                # Expect: status == "success" | "error" (script completed/failed)
                # Return: task_id + output summary (NOT full output)

                # Extract task_id from server response (NEW: unified task management)
                task_id = result.get("task_id")

                if status == "success":
                    # Script completed successfully
                    # Extract output and script result from server response
                    output = result.get("output", "")  # Captured stdout (print statements)
                    script_result = data  # Script's 'result' variable
                    start_time = result.get("start_time")
                    end_time = result.get("end_time")

                    # Use pagination utility to extract output summary (last 10 lines)
                    output_text, pagination = format_paginated_output(output, offset=0, limit=10)

                    # Build navigation hints
                    nav_hints = []
                    if pagination["has_earlier"]:
                        nav_hints.append(f"older: offset={10}")
                    nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                    # Build LLM-friendly text with summary
                    llm_text_parts = []

                    # 1. Success message with task_id and time range (matching list tool format)
                    base_message = result.get("message", "Script completed successfully")
                    time_info = format_time_range(start_time, end_time)
                    llm_text_parts.append(f"✓ {base_message} | {time_info}")
                    if task_id:
                        llm_text_parts.append(f"\nTask ID: {task_id}")

                    # 2. Output summary (last 10 lines by default)
                    if output:
                        llm_text_parts.append(
                            f"\n📊 Output: {pagination['total_lines']} lines total | "
                            f"Showing: last {pagination['displayed_count']} lines\n\n"
                            f"━━━ Output Summary ━━━\n"
                            f"{output_text}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 Navigate: {nav_hint}"
                        )

                    # 3. Structured result (if script defined 'result' variable)
                    if script_result is not None:
                        llm_text_parts.append(f"\n\n=== Script Result ===\n{script_result}")

                    llm_text = "".join(llm_text_parts)

                    return success_response(
                        message=result.get("message", f"Script executed: {script_path}"),
                        llm_content={
                            "parts": [{
                                "type": "text",
                                "text": llm_text
                            }]
                        },
                        script_path=script_path,
                        task_id=task_id,  # NEW: Enable post-execution query
                        script_result=script_result,
                        pagination=pagination  # Include pagination metadata
                    )

                else:
                    # Script execution failed (status == "error" or other)
                    # Extract output even on error (useful for debugging)
                    output = result.get("output", "")  # Captured stdout before error
                    error_message = result.get("message", "Script execution failed")
                    start_time = result.get("start_time")
                    end_time = result.get("end_time")

                    # Use pagination utility to extract output summary (last 10 lines)
                    output_text, pagination = format_paginated_output(output, offset=0, limit=10)

                    # Build navigation hints
                    nav_hints = []
                    if pagination["has_earlier"]:
                        nav_hints.append(f"older: offset={10}")
                    nav_hint = " | ".join(nav_hints) if nav_hints else "all output shown"

                    # Build LLM content with error message and output summary
                    llm_text_parts = []

                    # 1. Error message with task_id and time range (matching list tool format)
                    time_info = format_time_range(start_time, end_time)
                    llm_text_parts.append(f"✗ {error_message} | {time_info}")
                    if task_id:
                        llm_text_parts.append(f"\nTask ID: {task_id}")

                    # 2. Script output before error (summary) - helps with debugging
                    if output:
                        llm_text_parts.append(
                            f"\n📊 Output: {pagination['total_lines']} lines total | "
                            f"Showing: last {pagination['displayed_count']} lines\n\n"
                            f"━━━ Output before error ━━━\n"
                            f"{output_text}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 Navigate: {nav_hint}"
                        )

                    llm_text = "".join(llm_text_parts)

                    return success_response(
                        message=result.get("message", f"Script error: {script_path}"),
                        llm_content={
                            "parts": [{
                                "type": "text",
                                "text": llm_text
                            }]
                        },
                        script_path=script_path,
                        task_id=task_id,  # NEW: Enable post-execution query
                        script_error=error_message,
                        pagination=pagination  # Include pagination metadata
                    )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error executing script: {str(e)}")

    print(f"[DEBUG] Registered PFC script tool: pfc_execute_script")
