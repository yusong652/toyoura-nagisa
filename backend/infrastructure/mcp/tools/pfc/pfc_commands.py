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
                "PFC command name (e.g., 'model gravity', 'contact cmat default', 'ball create')"
            )
        ),
        arg: Optional[str] = Field(
            None,
            description=(
                "Optional positional argument (value without keyword).\n"
                "Used for simple value-based commands.\n"
                "Examples:\n"
                "  • \"9.81\" → model gravity 9.81\n"
                "  • \"(0,0,-9.81)\" → model gravity (0,0,-9.81)\n"
                "  • \"stop\" → domain condition stop"
            )
        ),
        params: Optional[str] = Field(
            None,
            description=(
                "Optional JSON object with keyword parameters. "
                "Value can be a string, number, or null:\n"
                "  • String value: {\"extent\": \"-10 10 -10 10 -10 10\"}\n"
                "  • String identifier: {\"model\": \"linear\"}\n"
                "  • Numeric value: {\"proximity\": 0.5}\n"
                "  • Boolean flag (null): {\"inheritance\": null}\n"
                "  • Tuple string: {\"position\": \"(0, 0, 0)\"}\n"
                "  • Identifier with quotes: {\"group\": \"my_balls\"}\n"
                "Examples:\n"
                "  • {\"model\": \"linear\", \"inheritance\": null}\n"
                "  • {\"radius\": 1.0, \"position\": \"(0,0,0)\", \"group\": \"balls\"}"
            )
        )
    ) -> Dict[str, Any]:
        """
        Execute a native PFC command through the WebSocket connection to PFC server.

        This tool executes native ITASCA PFC commands supporting both positional argument
        and keyword parameters. PFC commands have flexible syntax allowing:
        - Positional value without keyword
        - Keyword-value pairs
        - Boolean flags (keywords without values)

        Args:
            command: PFC command name (e.g., "model gravity", "contact cmat default", "ball create")
            arg: Optional positional argument (single value without keyword)
            params: Optional JSON object with keyword parameters (values can be string, number, or null)

        Examples:
            # Positional argument - gravity with scalar
            pfc_execute_command(command="model gravity", arg="9.81")
            # Assembled: model gravity 9.81

            # Positional argument - gravity with vector
            pfc_execute_command(command="model gravity", arg="(0,0,-9.81)")
            # Assembled: model gravity (0,0,-9.81)

            # Keyword arguments - domain extent
            pfc_execute_command(
                command="model domain",
                params='{"extent": "-10 10 -10 10 -10 10"}'
            )
            # Assembled: model domain extent -10 10 -10 10 -10 10

            # Boolean flags - contact material default with inheritance
            pfc_execute_command(
                command="contact cmat default",
                params='{"model": "linear", "inheritance": null}'
            )
            # Assembled: contact cmat default model linear inheritance

            # Ball creation with keyword parameters
            pfc_execute_command(
                command="ball create",
                params='{"radius": 1.0, "position": "(0,0,0)", "group": "balls"}'
            )
            # Assembled: ball create radius 1.0 position (0,0,0) group "balls"

            # Simple command - no parameters
            pfc_execute_command(command="model cycle")
            # Assembled: model cycle

        Note:
            - All parameters are optional - commands use defaults if omitted
            - null values in params indicate boolean flags (keyword without value)
            - Server assembles final command from command + arg + params
        """
        try:
            # Parse parameters
            params_dict = json.loads(params) if params else {}

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute command (server will assemble command string from command + arg + params)
            result = await client.send_command(command, arg, params_dict)

            # Build display command string for logging
            parts = [command]

            # Add positional argument
            if arg:
                parts.append(str(arg))

            # Add keyword parameters
            if params_dict:
                for key, value in params_dict.items():
                    parts.append(key)
                    if value is not None:  # null values are boolean flags
                        parts.append(str(value))

            pfc_cmd = " ".join(parts)

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

    print(f"[DEBUG] Registered PFC command tool: pfc_execute_command")
