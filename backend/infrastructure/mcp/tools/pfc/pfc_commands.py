"""
PFC Command Tools - MCP tools for ITASCA PFC simulation control.

Provides a single unified tool for executing PFC commands through WebSocket.
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Optional
import json

from .websocket_client import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_pfc_tools(mcp: FastMCP):
    """
    Register PFC tools with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        tags={"pfc", "simulation", "itasca", "particle", "dem"},
        annotations={"category": "pfc", "tags": ["pfc", "simulation", "itasca"]}
    )
    async def pfc_execute_command(
        context: Context,
        command: str,
        params: Optional[str] = None
    ) -> dict:
        """
        Execute a PFC SDK command through the WebSocket connection to PFC server.

        This tool provides direct access to ITASCA PFC SDK commands. The command uses
        dot notation to access nested SDK objects (e.g., "ball.create", "cycle", "ball.list").

        Args:
            command: PFC SDK command in dot notation
                Examples:
                - "ball.create" - Create a ball particle
                - "cycle" - Run simulation cycles
                - "ball.list" - List all balls
                - "ball.num" - Get number of balls
                - "model.save" - Save model state
                - "model.restore" - Load model state
            params: Optional JSON string of command parameters
                Example: '{"radius": 0.5, "position": [0, 0, 0], "density": 2500}'

        Returns:
            dict: Standardized tool result with status and data

        Examples:
            # Create a ball
            pfc_execute_command(
                command="ball.create",
                params='{"radius": 0.5, "position": [0, 0, 0], "density": 2500}'
            )

            # Run 1000 cycles
            pfc_execute_command(
                command="cycle",
                params='{"steps": 1000}'
            )

            # Query balls
            pfc_execute_command(command="ball.list")

            # Save state
            pfc_execute_command(
                command="model.save",
                params='{"filename": "model_state.sav"}'
            )

        Note:
            - Requires PFC server running in PFC GUI/Console
            - Server must be started: server.start_background() in PFC Python shell
            - Commands are executed directly in PFC's itasca module
        """
        try:
            # Parse parameters
            param_dict = json.loads(params) if params else {}

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute command
            result = await client.send_command(command, param_dict)

            # Check execution status
            if result.get("status") == "success":
                return success_response(
                    message=result.get("message", f"PFC command '{command}' executed successfully"),
                    llm_content=f"✓ PFC command executed: {command}\nResult: {result.get('data')}",
                    data={
                        "command": command,
                        "result": result.get("data"),
                        "timestamp": result.get("timestamp")
                    }
                )
            else:
                return error_response(
                    message=result.get("message", "PFC command execution failed"),
                    error_detail=result.get("error", "Unknown error"),
                    data={"command": command}
                )

        except ConnectionError as e:
            return error_response(
                message="PFC server not connected",
                error_detail=str(e),
                data={
                    "command": command,
                    "hint": "Start PFC server with: server.start_background() in PFC Python shell"
                }
            )

        except json.JSONDecodeError as e:
            return error_response(
                message="Invalid parameters JSON",
                error_detail=str(e),
                data={"command": command, "params": params}
            )

        except Exception as e:
            return error_response(
                message=f"Failed to execute PFC command: {command}",
                error_detail=str(e),
                data={"command": command}
            )

    print(f"[DEBUG] Registered PFC tool: pfc_execute_command")
