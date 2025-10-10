"""
PFC Command Tools - MCP tools for ITASCA PFC simulation control.

Provides a single unified tool for executing PFC commands through WebSocket.
"""

from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Optional, Dict, Any, Union
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
        arg: Optional[Union[bool, int, float, str, tuple]] = Field(
            None,
            description=(
                "Optional positional argument (value without keyword) using native Python types.\n"
                "Common use cases:\n"
                "  • Boolean: True → model large-strain true\n"
                "  • Number: 9.81 → model gravity 9.81\n"
                "  • Tuple: (0, 0, -9.81) → model gravity (0,0,-9.81)\n"
                "Note: Most PFC commands use keyword parameters. "
                "Positional args are typically booleans, numeric values, or tuples."
            )
        ),
        params: Optional[Dict[str, Any]] = Field(
            None,
            description=(
                "Optional dictionary with keyword parameters using typed values.\n"
                "Value types:\n"
                "  • Integer: {\"number\": 100} → keyword number 100\n"
                "  • Float: {\"radius\": 1.5} → keyword radius 1.5\n"
                "  • Tuple/List: {\"position\": [0, 0, 0]}\n"
                "  • String identifier: {\"model\": \"linear\"}, {\"group\": \"balls\"}\n"
                "  • Complex string: {\"extent\": \"-10 10 -10 10 -10 10\"}\n"
                "  • Nested dict: {\"property\": {\"kn\": 1.0e6, \"dp_nratio\": 0.5}} → keyword property kn 1.0e6 dp_nratio 0.5\n"
                "Examples:\n"
                "  • {\"model\": \"linear\"}\n"
                "  • {\"radius\": 1.5, \"position\": [0, 0, 0], \"group\": \"balls\"}\n"
                "  • {\"model\": \"linear\", \"property\": {\"kn\": 1.0e6, \"dp_nratio\": 0.5, \"fric\": 0.5}}"
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
            arg: Optional positional argument using native Python types (bool, int, float, str, tuple)
            params: Optional dictionary with keyword parameters (values: bool, number, list, string, or None)

        Examples:
            # Positional argument - boolean
            pfc_execute_command(command="model large-strain", arg=True)
            # Assembled: model large-strain true

            # Positional argument - gravity with number
            pfc_execute_command(command="model gravity", arg=9.81)
            # Assembled: model gravity 9.81

            # Positional argument - gravity with tuple
            pfc_execute_command(command="model gravity", arg=(0, 0, -9.81))
            # Assembled: model gravity (0,0,-9.81)

            # Keyword arguments - domain extent
            pfc_execute_command(
                command="model domain",
                params={"extent": "-10 10 -10 10 -10 10"}
            )
            # Assembled: model domain extent -10 10 -10 10 -10 10

            # Boolean flags - contact material default with inheritance
            pfc_execute_command(
                command="contact cmat default",
                params={"model": "linear", "inheritance": None}
            )
            # Assembled: contact cmat default model linear inheritance

            # Ball creation with keyword parameters (native types)
            pfc_execute_command(
                command="ball create",
                params={"radius": 1.0, "position": [0, 0, 0], "group": "balls"}
            )
            # Assembled: ball create radius 1.0 position (0,0,0) group "balls"

            # Simple command - no parameters
            pfc_execute_command(command="model cycle")
            # Assembled: model cycle

        Note:
            - All parameters are optional - commands use defaults if omitted
            - arg accepts native Python types (bool, int, float, str, tuple) for type-driven formatting
            - params dict values support: bool, number, list (for tuples), string, or None (boolean flags)
            - Server performs type-driven command assembly from command + arg + params
            - Python True/False automatically converts to PFC true/false (lowercase, unquoted)
        """
        try:
            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute command (server will assemble command string from command + arg + params)
            result = await client.send_command(command, arg, params or {})

            # Build display command string for logging
            parts = [command]

            # Add positional argument
            if arg:
                parts.append(str(arg))

            # Add keyword parameters
            if params:
                for key, value in params.items():
                    parts.append(key)
                    if value is not None:  # None values are boolean flags
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

        except Exception as e:
            # Backend error - unexpected system error
            return error_response(f"System error executing PFC command: {str(e)}")

    print(f"[DEBUG] Registered PFC command tool: pfc_execute_command")
