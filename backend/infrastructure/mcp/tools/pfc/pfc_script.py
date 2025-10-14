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

                return success_response(
                    message=result.get("message", f"Script submitted: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"Task submitted: {script_name}\nTask ID: {task_id}\n\nUse pfc_check_task_status to monitor progress."
                        }]
                    },
                    script_path=script_path,
                    result=data
                )

            else:
                # ===== Foreground Mode (Synchronous) =====
                # Expect: status == "success" | "error" (script completed/failed)
                # Return: complete output and result

                if status == "success":
                    # Script completed successfully
                    # Extract output and script result from server response
                    output = result.get("output", "")  # Captured stdout (print statements)
                    script_result = data  # Script's 'result' variable

                    # Build comprehensive LLM content with output and result
                    llm_text_parts = []

                    # 1. Success message
                    base_message = result.get("message", "Script completed successfully")
                    llm_text_parts.append(base_message)

                    # 2. Script output (print statements) - KEY ENHANCEMENT for LLM visibility
                    if output and output.strip():
                        llm_text_parts.append(f"\n\n=== Script Output ===\n{output.strip()}")

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
                        output=output,  # Preserve raw output for frontend/debugging
                        script_result=script_result  # Preserve structured result
                    )

                else:
                    # Script execution failed (status == "error" or other)
                    # Extract output even on error (useful for debugging)
                    output = result.get("output", "")  # Captured stdout before error
                    error_message = result.get("message", "Script execution failed")

                    # Build LLM content with error message and any output captured before error
                    llm_text_parts = []

                    # 1. Error message
                    llm_text_parts.append(error_message)

                    # 2. Script output before error (if any) - helps with debugging
                    if output and output.strip():
                        llm_text_parts.append(f"\n\n=== Script Output (before error) ===\n{output.strip()}")

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
                        output=output,  # Preserve output for debugging
                        script_error=error_message
                    )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error executing script: {str(e)}")

    print(f"[DEBUG] Registered PFC script tool: pfc_execute_script")
