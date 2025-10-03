"""
PFC Command Tools - MCP tools for ITASCA PFC simulation control.

Provides a single unified tool for executing PFC commands through WebSocket.
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Optional, Dict, Any
import json
from pydantic import Field
from backend.infrastructure.pfc import get_client
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
        command: str = Field(
            ...,
            description=(
                "PFC command name in space"
                "Examples: 'ball create', 'model domain', 'model cycle'"
            )
        ),
        params: Optional[str] = Field(
            None,
            description=(
                "Optional JSON string with command keyword parameters. "
                "Use PFC native string formats:\n"
                "  • Tuple format: {\"position\": \"(0, 0, 0)\"} → position (0, 0, 0)\n"
                "  • Number sequence: {\"extent\": \"-10 10 -10 10 -10 10\"} → extent -10 10 -10 10 -10 10\n"
                "  • Identifier: {\"group\": \"my_balls\"} → group \"my_balls\"\n"
                "  • Numeric: {\"radius\": 1.5} → radius 1.5\n"
                "Examples: {\"radius\": 1.0, \"position\": \"(0, 0, 0)\", \"group\": \"balls\"}"
            )
        )
    ) -> Dict[str, Any]:
        """
        Execute a native PFC command through the WebSocket connection to PFC server.

        This tool executes native ITASCA PFC commands by combining the command name
        with optional keyword parameters. Commands use default values if parameters
        are not specified.

        Args:
            command: PFC command name (e.g., "ball create", "model domain", "cycle")
            params: Optional JSON with keyword-value pairs using PFC native formats

        Examples:
            # Create a ball with default parameters
            pfc_execute_command(command="ball create")

            # Create a ball with specific parameters (tuple string for position, identifier for group)
            pfc_execute_command(
                command="ball create",
                params='{"radius": 1.0, "position": "(0, 0, 0)", "group": "my_balls"}'
            )
            # Assembled: ball create radius 1.0 position (0, 0, 0) group "my_balls"

            # Set model domain (space-separated number sequence string)
            pfc_execute_command(
                command="model domain",
                params='{"extent": "-10 10 -10 10 -10 10"}'
            )
            # Assembled: model domain extent -10 10 -10 10 -10 10

            # Run cycles (numeric parameter)
            pfc_execute_command(command="model solve", params='{"cycles": 1000}')

        Note:
            - Parameters are optional - commands use defaults if omitted
            - Server assembles final command: "command keyword1 value1 keyword2 value2 ..."
        """
        try:
            # Parse parameters
            param_dict = json.loads(params) if params else {}

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute command (server will assemble command string from command + params)
            result = await client.send_command(command, param_dict)

            # Build display command string
            if param_dict:
                param_str = " ".join([f"{k} {v}" for k, v in param_dict.items()])
                pfc_cmd = f"{command} {param_str}"
            else:
                pfc_cmd = command

            # PFC always returns a valid response - both success and error are "successful tool execution"
            # The LLM needs to see what PFC returned, whether it's success or error
            if result.get("status") == "success":
                return success_response(
                    message=result.get("message", f"PFC command executed: {pfc_cmd}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"✓ PFC command executed: {pfc_cmd}\nResult: {result.get('data')}"
                        }]
                    },
                    command=pfc_cmd,
                    result=result.get("data")
                )
            else:
                # PFC error (syntax error, invalid parameters, etc.) - still a successful tool call
                return success_response(
                    message=result.get("message", f"PFC command error: {pfc_cmd}"),
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"⚠ PFC command returned error: {pfc_cmd}\nError: {result.get('message')}"
                        }]
                    },
                    command=pfc_cmd,
                    pfc_error=result.get("message")
                )

        except ConnectionError as e:
            # Backend error - connection to PFC server failed
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except json.JSONDecodeError as e:
            # Backend error - invalid JSON in params
            return error_response(f"Invalid JSON in params: {str(e)}")

        except Exception as e:
            # Backend error - unexpected system error
            return error_response(f"System error executing PFC command: {str(e)}")

    print(f"[DEBUG] Registered PFC tool: pfc_execute_command")
