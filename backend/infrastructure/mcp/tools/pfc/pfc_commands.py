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
                "Optional dictionary with keyword parameters.\n"
                "Value types:\n"
                "  • Integer: {\"number\": 100}\n"
                "  • Float: {\"radius\": 1.5}\n"
                "  • List/Tuple: {\"position\": [0, 0, 0]}\n"
                "  • String: {\"model\": \"linear\"}, {\"group\": \"balls\"}\n"
                "  • Nested dict: {\"property\": {\"kn\": 1.0e6, \"dp_nratio\": 0.5, \"fric\": 0.5}}\n"
                "Examples:\n"
                "  • {\"model\": \"linear\"}\n"
                "  • {\"radius\": 1.5, \"position\": [0, 0, 0], \"group\": \"balls\"}\n"
                "  • {\"property\": {\"kn\": 1.0e6, \"dp_nratio\": 0.5, \"fric\": 0.5}}"
            )
        ),
        timeout: int = Field(
            default=30000,
            description=(
                "Command execution timeout in milliseconds. Valid range: 1000-600000 (1s to 10min). "
                "Only applies when run_in_background=False. "
                "Recommended: 5000-10000ms for quick tests, 30000-60000ms for model solve/cycle. "
                "For long cycles, use run_in_background=True instead of increasing timeout."
            )
        ),
        run_in_background: bool = Field(
            default=False,
            description=(
                "Set to true to return task_id immediately and run in background. "
                "When false, waits for completion and catches errors immediately (recommended for testing). "
                "Query progress with pfc_check_task_status when using background mode."
            )
        )
    ) -> Dict[str, Any]:
        """
        Execute PFC commands with success/failure validation only.

        This tool returns only command execution status (success or syntax error).
        Use for validation and state modification without data inspection.

        Note:
            For operations requiring Python SDK access, custom logic, or print() output,
            use pfc_execute_script instead.
        """
        try:
            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Execute command (server will assemble command string from command + arg + params)
            # WebSocket timeout is auto-calculated based on timeout + infrastructure buffer
            result = await client.send_command(
                command=command,
                arg=arg,
                params=params or {},
                timeout_ms=timeout,
                run_in_background=run_in_background
            )

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
