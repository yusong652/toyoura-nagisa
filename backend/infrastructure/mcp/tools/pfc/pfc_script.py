"""
PFC Script Tools - MCP tool for executing Python SDK scripts.

Provides script execution functionality for PFC Python SDK operations
that return data (unlike native commands which don't return values).
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any
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
        )
    ) -> Dict[str, Any]:
        """
        Execute Python SDK script for long-running simulations and analysis.

        This tool executes Python scripts that use PFC Python SDK (itasca module).
        Scripts run as long-running tasks and return immediately with a task_id.

        Data flow pattern (three channels):
            1. Real-time monitoring: Scripts print progress; check output via pfc_check_task_status
            2. Checkpoint persistence: Scripts save complete state with "model save"
            3. Analysis data: Scripts export CSV/JSON; write analysis scripts to process (don't read CSV directly)

        Usage workflow:
            1. Read script file to understand what it does
            2. Call this tool with script path → get task_id
            3. Monitor progress with pfc_check_task_status (see print output)
            4. After completion, process exported files

        Examples:
            # Submit long-running simulation
            result = pfc_execute_script(script_path="/workspace/scripts/settling_sim.py")
            task_id = result["data"]["task_id"]

            # Monitor progress (check print output)
            pfc_check_task_status(task_id=task_id)

            # After completion: read metadata, analyze exported CSV with bash/Python if needed

        Note:
            For simple commands, use pfc_execute_command instead.
        """
        try:
            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute script
            result = await client.send_script(script_path)

            # Handle result
            if result.get("status") == "success":
                return success_response(
                    message=result.get("message", f"Script executed: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"✓ {result.get('message', 'Script executed successfully')}"
                        }]
                    },
                    script_path=script_path,
                    result=result.get("data")
                )
            else:
                # Script error - still successful tool call
                return success_response(
                    message=result.get("message", f"Script error: {script_path}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"⚠ {result.get('message', 'Script execution failed')}"
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
