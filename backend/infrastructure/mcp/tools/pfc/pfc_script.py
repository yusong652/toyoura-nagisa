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
                "Example: '/path/to/pfc_project/scripts/analyze_balls.py'. "
                "LLM should read the script first to understand its functionality."
            )
        )
    ) -> Dict[str, Any]:
        """
        Execute Python SDK script from file path for queries and advanced operations.

        This tool executes Python scripts that use PFC Python SDK (itasca module),
        enabling queries and operations that return data (unlike commands which don't).

        Workflow:
            1. LLM reads script file content using Read tool
            2. LLM understands what the script does
            3. LLM calls this tool with script path
            4. PFC server reads and executes the script locally
            5. Returns result data

        Args:
            script_path: Absolute path to Python script file

        Examples:
            # First, LLM reads the script to understand it
            # Then executes:
            pfc_execute_script(script_path="/pfc_project/scripts/get_ball_count.py")

            # Script content example (get_ball_count.py):
            # result = itasca.ball.count()

        Note:
            - Script must define 'result' variable or be single expression
            - Script has access to 'itasca' module
            - Use for queries (ball.count(), ball.list()) not commands
            - For native PFC commands, use pfc_execute_command instead
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
