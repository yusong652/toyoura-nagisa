"""
PFC Script Executor - Executes Python SDK scripts with direct API access.

This module provides script execution functionality using PFC Python SDK via
main thread queue, enabling queries and operations that return values.

Python 3.6 compatible implementation.
"""

import asyncio
import logging
import sys
from io import StringIO
from typing import Any, Dict

from .main_thread_executor import MainThreadExecutor

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCScriptExecutor:
    """Execute Python scripts using PFC Python SDK via main thread queue."""

    def __init__(self, main_executor, task_manager):
        # type: (MainThreadExecutor, Any) -> None
        """
        Initialize executor with itasca module, main thread executor, and task manager.

        Args:
            main_executor: Main thread executor for queue-based execution
            task_manager: Task manager for long-running task tracking
        """
        self.main_executor = main_executor
        self.task_manager = task_manager

        try:
            import itasca  # type: ignore
            self.itasca = itasca
            logger.info("✓ ITASCA SDK loaded for script execution")
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available for script execution")
            self.itasca = None

    def _execute_script_sync(self, script_path, script_content, output_buffer):
        # type: (str, str, Any) -> Dict[str, Any]
        """
        Execute Python script synchronously (called in main thread).

        Captures stdout during execution for progress tracking using shared buffer.

        Args:
            script_path: Path to script (for error messages)
            script_content: Script content to execute
            output_buffer: StringIO buffer for capturing stdout (shared with TaskManager)

        Returns:
            Result dictionary with status, message, data, and output:
                - status: "success" or "error"
                - message: User-friendly message
                - data: Script result (from 'result' variable)
                - output: Captured stdout content (print statements)
        """
        import os

        # Use shared output buffer for stdout capture
        old_stdout = sys.stdout
        sys.stdout = output_buffer

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

            # Get captured output from shared buffer
            output_text = output_buffer.getvalue()

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
                "data": serialized_result,
                "output": output_text  # Include captured output
            }

        except Exception as e:
            # Get captured output even on error
            output_text = output_buffer.getvalue()

            logger.error("Script execution failed: {}".format(e))
            return {
                "status": "error",
                "message": "Script execution failed: {}".format(str(e)),
                "data": None,
                "output": output_text  # Include output up to error point
            }

        finally:
            # Always restore stdout
            sys.stdout = old_stdout

    async def execute_script(self, script_path):
        # type: (str) -> Dict[str, Any]
        """
        Submit Python script for execution as a long-running task.

        Scripts are always treated as long-running tasks and return immediately
        with a task_id. Use check_task_status to query progress and retrieve output.

        Args:
            script_path: Absolute path to Python script file
                Example: "/path/to/pfc_project/scripts/analyze_balls.py"

        Returns:
            Result dictionary for task submission:
                - status: "pending" - Task submitted successfully
                - message: str - Submission confirmation message
                - data: Dict with task_id and script_path

        Note:
            - Scripts are executed in IPython main thread via queue
            - Script must define 'result' variable for structured data
            - Print statements are captured and available via task status query
            - Script has access to 'itasca' module in global scope
        """
        import os

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

            # Submit to main thread queue (non-blocking)
            script_name = os.path.basename(script_path)
            logger.info("Submitting script as long-running task: {}".format(script_name))

            # Create shared output buffer for real-time output capture
            output_buffer = StringIO()

            future = self.main_executor.submit(
                self._execute_script_sync,
                script_path,
                script_content,
                output_buffer  # Pass shared buffer to executor
            )

            # Register with task manager as script task and return immediately
            task_id = self.task_manager.create_script_task(
                future,
                script_name,
                script_path,
                output_buffer  # Pass buffer reference for live status queries
            )

            return {
                "status": "pending",
                "message": "Script submitted as long-running task: {}\nUse check_task_status tool to query progress and retrieve output.".format(script_name),
                "data": {
                    "task_id": task_id,
                    "script_path": script_path,
                    "script_name": script_name
                }
            }

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
