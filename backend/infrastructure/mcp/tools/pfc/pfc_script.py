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
        from pathlib import Path

        try:
            # Normalize path for consistency (convert to forward slashes)
            # This ensures consistent path format across platforms
            script_path = str(Path(script_path)).replace('\\', '/')

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
            status = result.get("status")
            data = result.get("data")

            if status == "pending":
                # Background mode: provide task_id and monitoring guidance
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
            elif status == "success":
                # Synchronous mode: script completed successfully
                return success_response(
                    message=result.get("message", f"Script executed: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": result.get("message", "Script completed successfully")
                        }]
                    },
                    script_path=script_path,
                    result=data
                )
            else:
                # Script error - still successful tool call
                return success_response(
                    message=result.get("message", f"Script error: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": result.get("message", "Script execution failed")
                        }]
                    },
                    script_path=script_path,
                    script_error=result.get("message")
                )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"System error executing script: {str(e)}")

    print(f"[DEBUG] Registered PFC script tool: pfc_execute_script")
