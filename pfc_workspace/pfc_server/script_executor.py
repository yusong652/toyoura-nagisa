"""
PFC Script Executor - Executes Python SDK scripts with direct API access.

This module provides script execution functionality using PFC Python SDK,
enabling queries and operations that return values (unlike command execution).
"""

import logging
from typing import Any, Dict

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCScriptExecutor:
    """Execute Python scripts using PFC Python SDK."""

    def __init__(self):
        """Initialize executor with itasca module reference."""
        try:
            import itasca  # type: ignore
            self.itasca = itasca
            logger.info("✓ ITASCA SDK loaded for script execution")
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available for script execution")
            self.itasca = None

    async def execute_script(self, script_path: str) -> Dict[str, Any]:
        """
        Execute Python script from file path and return the result.

        This method reads and executes Python script files using the itasca module,
        enabling direct access to PFC Python SDK methods that return values.

        Args:
            script_path: Absolute path to Python script file
                Example: "/path/to/pfc_project/scripts/analyze_balls.py"

        Returns:
            Result dictionary following ToolResult pattern:
                - status: Literal["success", "error"] - Operation outcome
                - message: str - User-friendly message with result
                - data: Any - Script execution result (serialized)

        Note:
            - Script must define 'result' variable or use single expression
            - Script has access to 'itasca' module in global scope
            - LLM should read script content first to understand functionality
        """
        try:
            if not self.itasca:
                return {
                    "status": "error",
                    "message": "ITASCA SDK not available: Server not running in PFC GUI environment",
                    "data": None
                }

            # Read script file
            logger.info(f"Reading script file: {script_path}")
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
            except FileNotFoundError:
                return {
                    "status": "error",
                    "message": f"Script file not found: {script_path}",
                    "data": None
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Failed to read script file: {str(e)}",
                    "data": None
                }

            logger.info(f"Executing Python script from: {script_path}")

            # Prepare execution context with itasca module
            exec_globals = {"itasca": self.itasca}
            exec_locals = {}

            # Try to execute as expression first (single line, returns value)
            try:
                result = eval(script_content, exec_globals, exec_locals)
            except SyntaxError:
                # If eval fails, try exec (multi-line script)
                exec(script_content, exec_globals, exec_locals)
                # Look for 'result' variable in locals
                result = exec_locals.get('result', None)

            # Serialize result for response
            serialized_result = self._serialize_result(result)

            # Build message with result
            import os
            script_name = os.path.basename(script_path)
            if serialized_result is not None:
                message = f"Script executed: {script_name}\nResult: {serialized_result}"
            else:
                message = f"Script executed: {script_name}"

            return {
                "status": "success",
                "message": message,
                "data": serialized_result
            }

        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return {
                "status": "error",
                "message": f"Script execution failed: {str(e)}",
                "data": None
            }

    def _serialize_result(self, result: Any) -> Any:
        """
        Convert PFC objects to JSON-serializable format.

        Args:
            result: Any Python object returned from script execution

        Returns:
            JSON-serializable representation of the result
        """
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
