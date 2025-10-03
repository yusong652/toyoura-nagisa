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
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a PFC command and return the result.

        Args:
            command: Command in dot notation (e.g., "ball.create", "cycle.run")
            params: Command parameters dictionary

        Returns:
            Result dictionary with structure:
                - status: "success" or "error"
                - data: Command result data
                - message: Human-readable message
                - error: Error details if status="error"
        """
        try:
            if not self.itasca:
                return {
                    "status": "error",
                    "message": "ITASCA SDK not available",
                    "error": "Server not running in PFC GUI environment"
                }

            logger.info(f"Executing command: {command} with params: {params}")

            # Special case: "command" executes a PFC command string
            if command == "command" and "cmd" in params:
                cmd_str = params["cmd"]
                logger.info(f"Executing PFC command string: {cmd_str}")
                result = self.itasca.command(cmd_str)
                return {
                    "status": "success",
                    "data": self._serialize_result(result),
                    "message": f"PFC command executed: {cmd_str}"
                }

            # Parse command path (e.g., "ball.create" -> itasca.ball.create)
            parts = command.split('.')
            obj = self.itasca

            for part in parts[:-1]:
                obj = getattr(obj, part)

            # Execute the command
            func = getattr(obj, parts[-1])

            # Call function with parameters
            if callable(func):
                result = func(**params)
            else:
                result = func

            return {
                "status": "success",
                "data": self._serialize_result(result),
                "message": f"Command '{command}' executed successfully"
            }

        except AttributeError as e:
            logger.error(f"Command not found: {command} - {e}")
            return {
                "status": "error",
                "message": f"Command '{command}' not found in ITASCA SDK",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "status": "error",
                "message": f"Command execution failed",
                "error": str(e)
            }

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
