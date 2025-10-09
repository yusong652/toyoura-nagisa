"""
PFC Script Executor - Executes Python SDK scripts with direct API access.

This module provides script execution functionality using PFC Python SDK via
main thread queue, enabling queries and operations that return values.

Python 3.6 compatible implementation.
"""

import asyncio
import logging
from typing import Any, Dict

from .main_thread_executor import MainThreadExecutor

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCScriptExecutor:
    """Execute Python scripts using PFC Python SDK via main thread queue."""

    def __init__(self, main_executor):
        # type: (MainThreadExecutor) -> None
        """
        Initialize executor with itasca module and main thread executor.

        Args:
            main_executor: Main thread executor for queue-based execution
        """
        self.main_executor = main_executor

        try:
            import itasca  # type: ignore
            self.itasca = itasca
            logger.info("✓ ITASCA SDK loaded for script execution")
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available for script execution")
            self.itasca = None

    def _execute_script_sync(self, script_path, script_content):
        # type: (str, str) -> Dict[str, Any]
        """
        Execute Python script synchronously (called in main thread).

        Args:
            script_path: Path to script (for error messages)
            script_content: Script content to execute

        Returns:
            Result dictionary with status, message, and data
        """
        import os

        try:
            logger.info("Executing Python script in main thread: {}".format(script_path))

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
            script_name = os.path.basename(script_path)
            if serialized_result is not None:
                message = "Script executed: {}\nResult: {}".format(
                    script_name, serialized_result
                )
            else:
                message = "Script executed: {}".format(script_name)

            return {
                "status": "success",
                "message": message,
                "data": serialized_result
            }

        except Exception as e:
            logger.error("Script execution failed: {}".format(e))
            return {
                "status": "error",
                "message": "Script execution failed: {}".format(str(e)),
                "data": None
            }

    async def execute_script(self, script_path):
        # type: (str) -> Dict[str, Any]
        """
        Execute Python script from file path via main thread queue.

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
            - All execution happens in IPython main thread via queue
        """
        try:
            if not self.itasca:
                return {
                    "status": "error",
                    "message": "ITASCA SDK not available: Server not running in PFC GUI environment",
                    "data": None
                }

            # Read script file
            logger.info("Reading script file: {}".format(script_path))
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
            except FileNotFoundError:
                return {
                    "status": "error",
                    "message": "Script file not found: {}".format(script_path),
                    "data": None
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": "Failed to read script file: {}".format(str(e)),
                    "data": None
                }

            # Submit to main thread queue
            logger.info("Submitting script to main thread: {}".format(script_path))
            future = self.main_executor.submit(
                self._execute_script_sync,
                script_path,
                script_content
            )

            # Wait for main thread to execute (async)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Use default thread pool
                future.result,  # Block until main thread processes
                300  # 5 minutes timeout
            )

            return result

        except Exception as e:
            logger.error("Script submission failed: {}".format(e))
            return {
                "status": "error",
                "message": "Script submission failed: {}".format(str(e)),
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
