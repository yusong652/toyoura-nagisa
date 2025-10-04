"""
PFC Command Executor - Executes ITASCA PFC commands via SDK.

This module provides command execution functionality for the PFC WebSocket server.
"""

import logging
from typing import Any, Dict

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCCommandExecutor:
    """Execute PFC commands using itasca SDK."""

    def __init__(self):
        """Initialize executor with itasca module reference."""
        try:
            import itasca  # type: ignore
            self.itasca = itasca
            logger.info("✓ ITASCA SDK loaded")
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available")
            self.itasca = None

    async def execute_command(
        self,
        command: str,
        arg: Any = None,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a native PFC command and return the result.

        This method assembles a complete PFC command string from the command name,
        optional positional argument, and optional keyword parameters, then executes
        via itasca.command().

        Args:
            command: PFC command name (e.g., "model gravity", "contact cmat default", "ball create")
            arg: Optional single positional argument (value without keyword)
                Example: "9.81" for "model gravity 9.81"
                Example: "(0,0,-9.81)" for "model gravity (0,0,-9.81)"
            params: Optional dictionary with keyword parameters (values can be None for boolean flags)
                Example: {"radius": 1.0, "position": "(0, 0, 0)", "group": "my_balls"}
                Example: {"model": "linear", "inheritance": None} for boolean flags
                Empty dict {} or None means use command defaults

        Returns:
            Result dictionary following ToolResult pattern:
                - status: Literal["success", "error"] - Operation outcome
                - message: str - User-friendly message (success description or error details)
                - data: Optional[Any] - Command result data (success only)
        """
        try:
            if not self.itasca:
                return {
                    "status": "error",
                    "message": "ITASCA SDK not available: Server not running in PFC GUI environment",
                    "data": None
                }

            # Assemble complete PFC command string
            params = params or {}  # Handle None params
            cmd_str = self._assemble_command(command, arg, params)
            logger.info(f"Executing PFC command: {cmd_str}")

            # Execute native PFC command
            result = self.itasca.command(cmd_str)

            # Serialize result for response
            serialized_result = self._serialize_result(result)

            # Build message based on whether there's a return value
            if serialized_result is not None:
                message = f"PFC command executed: {cmd_str}\nResult: {serialized_result}"
            else:
                message = f"PFC command executed: {cmd_str}"

            return {
                "status": "success",
                "message": message,
                "data": serialized_result
            }

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "status": "error",
                "message": f"Command execution failed: {str(e)}",
                "data": None
            }

    def _assemble_command(self, command: str, arg: Any, params: Dict[str, Any]) -> str:
        """
        Assemble complete PFC command string from command name, positional arg, and parameters.

        Args:
            command: PFC command name (e.g., "model gravity", "contact cmat default", "ball create")
            arg: Optional positional argument (single value without keyword)
            params: Keyword-value pairs for command parameters (None values are boolean flags)

        Returns:
            Complete PFC command string

        Examples:
            >>> _assemble_command("model gravity", "9.81", {})
            "model gravity 9.81"

            >>> _assemble_command("ball create", None, {"radius": 1.0, "position": "(0, 0, 0)"})
            "ball create radius 1.0 position (0, 0, 0)"

            >>> _assemble_command("contact cmat default", None, {"model": "linear", "inheritance": None})
            "contact cmat default model linear inheritance"
        """
        # Start with base command
        cmd_parts = [command]

        # Add positional argument (single value)
        if arg is not None:
            cmd_parts.append(str(arg))

        # Add keyword-value pairs (type-based formatting)
        for keyword, value in params.items():
            cmd_parts.append(keyword)

            # Handle None as boolean flag (keyword only, no value)
            if value is None:
                continue

            # Format value based on type
            if isinstance(value, str):
                # String type: check if it's PFC native format or identifier
                if (value.startswith('(') or                    # Tuple: "(0, 0, 0)"
                    value.startswith('-') or                    # Negative number sequence: "-10 10"
                    (value and value[0].isdigit()) or          # Positive number sequence: "10 20"
                    ' ' in value):                             # Multi-token sequence: "id 1 2"
                    # PFC native format → use as-is
                    value_str = value
                else:
                    # Single identifier → add quotes (PFC requirement)
                    value_str = f'"{value}"'
            elif isinstance(value, (int, float)):
                # Numeric type → direct conversion, no quotes
                value_str = str(value)
            else:
                # Fallback: string representation
                value_str = str(value)

            cmd_parts.append(value_str)

        return " ".join(cmd_parts)

    def _serialize_result(self, result: Any) -> Any:
        """Convert PFC objects to JSON-serializable format."""
        if result is None:
            return None
        elif isinstance(result, (str, int, float, bool)):
            return result
        elif isinstance(result, (list, tuple)):
            return [self._serialize_result(item) for item in result]
        elif isinstance(result, dict):
            return {k: self._serialize_result(v) for k, v in result.items()}
        else:
            # For complex PFC objects, return string representation
            return str(result)
