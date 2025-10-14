"""
Task Type Implementations - Concrete task classes for different execution types.

This module contains CommandTask and ScriptTask implementations, providing
type-specific behavior for command execution and script execution with output capture.

Python 3.6 compatible implementation.
"""

import logging
from typing import Any, Dict, Optional

from .task_base import Task

# Module logger
logger = logging.getLogger("PFC-Server")


class CommandTask(Task):
    """
    Task for PFC command execution.

    Simple task type without output capture, suitable for immediate
    commands that return results directly.
    """

    def __init__(self, task_id, future, command):
        # type: (str, Any, str) -> None
        """
        Initialize command task.

        Args:
            task_id: Unique task identifier
            future: asyncio Future object for the task
            command: PFC command string being executed
        """
        super(CommandTask, self).__init__(task_id, future, command, "command")
        self.command = command

        logger.info("✓ Command task registered: {} (ID: {})".format(command, task_id))

    def get_status_response(self):
        # type: () -> Dict[str, Any]
        """Get command task status with result data."""
        elapsed_time = self.get_elapsed_time()

        if self.status == "running":
            # Task still executing
            return {
                "status": "running",
                "message": "Command still executing: {}\nElapsed time: {:.2f}s".format(
                    self.description, elapsed_time
                ),
                "data": {
                    "task_id": self.task_id,
                    "task_type": self.task_type,
                    "description": self.description,
                    "elapsed_time": elapsed_time
                }
            }

        # Task completed or failed - retrieve result
        try:
            result = self.future.result(timeout=0)
        except Exception as e:
            result = None
            if self.status == "completed":
                logger.warning("Status mismatch for task {}: status='completed' but future raised: {}".format(
                    self.task_id, str(e)
                ))

        if self.status == "completed":
            # Command completed successfully
            logger.info("✓ Task completed: {} (ID: {}, Time: {:.2f}s)".format(
                self.description, self.task_id, elapsed_time
            ))

            # Serialize result data
            serialized_result = self._serialize_result(result)

            # Build response
            if serialized_result is not None:
                message = "Command completed: {}\nElapsed time: {:.2f}s\nResult: {}".format(
                    self.description, elapsed_time, serialized_result
                )
            else:
                message = "Command completed: {}\nElapsed time: {:.2f}s".format(
                    self.description, elapsed_time
                )

            response_data = serialized_result if isinstance(serialized_result, dict) else {}
            if not isinstance(response_data, dict):
                response_data = {"result": serialized_result}
            response_data["elapsed_time"] = elapsed_time

            return {
                "status": "success",
                "message": message,
                "data": response_data
            }

        else:  # status == "failed"
            # Command failed
            logger.error("✗ Command task failed: {} (ID: {})".format(self.description, self.task_id))

            error_msg = "Task execution failed"
            message = "Command failed: {}\nElapsed time: {:.2f}s\nError: {}".format(
                self.description, elapsed_time, error_msg
            )

            return {
                "status": "error",
                "message": message,
                "data": {"error": error_msg, "elapsed_time": elapsed_time}
            }

    def get_task_info(self):
        # type: () -> Dict[str, Any]
        """Get command task summary for listing."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "status": self.status,
            "elapsed_time": self.get_elapsed_time()
        }


class ScriptTask(Task):
    """
    Task for Python script execution.

    Enhanced task type with real-time output capture via StringIO buffer,
    suitable for long-running simulations with progress monitoring.
    """

    def __init__(self, task_id, future, script_name, script_path=None, output_buffer=None):
        # type: (str, Any, str, Optional[str], Any) -> None
        """
        Initialize script task.

        Args:
            task_id: Unique task identifier
            future: asyncio Future object for the task
            script_name: Name of the script file (e.g., "simulation.py")
            script_path: Optional full path to script for reference
            output_buffer: Optional StringIO buffer for real-time output capture
        """
        super(ScriptTask, self).__init__(task_id, future, "script: {}".format(script_name), "script")
        self.script_name = script_name
        self.script_path = script_path
        self.output_buffer = output_buffer

        logger.info("✓ Script task registered: {} (ID: {})".format(script_name, task_id))

    def get_current_output(self):
        # type: () -> Optional[str]
        """Get current output from buffer (for running scripts)."""
        if self.output_buffer:
            try:
                return self.output_buffer.getvalue()
            except Exception as e:
                logger.warning("Failed to read output buffer: {}".format(e))
        return None

    def get_status_response(self):
        # type: () -> Dict[str, Any]
        """Get script task status with output and result data."""
        elapsed_time = self.get_elapsed_time()

        if self.status == "running":
            # Task still executing - include current output
            current_output = self.get_current_output()

            response_data = {
                "task_id": self.task_id,
                "task_type": self.task_type,
                "description": self.description,
                "elapsed_time": elapsed_time
            }

            if current_output:
                response_data["output"] = current_output

            return {
                "status": "running",
                "message": "Script still executing: {}\nElapsed time: {:.2f}s".format(
                    self.description, elapsed_time
                ),
                "data": response_data
            }

        # Task completed or failed - retrieve result for status/data only
        # Output is ALWAYS retrieved from buffer (single source of truth)
        try:
            result = self.future.result(timeout=0)
        except Exception as e:
            result = None
            if self.status == "completed":
                logger.warning("Status mismatch for task {}: status='completed' but future raised: {}".format(
                    self.task_id, str(e)
                ))

        if self.status == "completed":
            # Script completed successfully
            logger.info("✓ Task completed: {} (ID: {}, Time: {:.2f}s)".format(
                self.description, self.task_id, elapsed_time
            ))

            # Get output from buffer (single source of truth)
            output_text = self.get_current_output()

            # Extract only status and data from result
            result_data = None
            result_status = "success"

            if isinstance(result, dict):
                result_data = result.get("data")
                result_status = result.get("status", "success")
            else:
                result_data = result

            # Serialize result data
            serialized_result = self._serialize_result(result_data)

            # Build message with output
            if output_text:
                message = "Script execution completed: {}\nElapsed time: {:.2f}s\n\n=== Script Output ===\n{}".format(
                    self.script_name, elapsed_time, output_text
                )
            elif serialized_result is not None:
                message = "Script completed: {}\nElapsed time: {:.2f}s\nResult: {}".format(
                    self.description, elapsed_time, serialized_result
                )
            else:
                message = "Script completed: {}\nElapsed time: {:.2f}s".format(
                    self.description, elapsed_time
                )

            # Build response data (always include output field for scripts)
            response_data = serialized_result if isinstance(serialized_result, dict) else {}
            if not isinstance(response_data, dict):
                response_data = {"result": serialized_result}
            response_data["output"] = output_text if output_text else ""
            response_data["elapsed_time"] = elapsed_time

            return {
                "status": result_status,
                "message": message,
                "data": response_data
            }

        else:  # status == "failed"
            # Script failed
            logger.error("✗ Script task failed: {} (ID: {})".format(self.description, self.task_id))

            # Get output from buffer (single source of truth)
            output_text = self.get_current_output()

            # Extract only error message from result
            error_msg = "Task execution failed"
            if isinstance(result, dict):
                error_msg = result.get("message", error_msg)

            # Build error message with partial output
            if output_text:
                message = "Script execution failed: {}\nElapsed time: {:.2f}s\nError: {}\n\n=== Partial Output ===\n{}".format(
                    self.script_name, elapsed_time, error_msg, output_text
                )
                error_data = {"error": error_msg, "output": output_text, "elapsed_time": elapsed_time}
            else:
                message = "Script failed: {}\nElapsed time: {:.2f}s\nError: {}".format(
                    self.description, elapsed_time, error_msg
                )
                error_data = {"error": error_msg, "elapsed_time": elapsed_time}

            return {
                "status": "error",
                "message": message,
                "data": error_data
            }

    def get_task_info(self):
        # type: () -> Dict[str, Any]
        """Get script task summary for listing."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "status": self.status,
            "elapsed_time": self.get_elapsed_time(),
            "script_name": self.script_name
        }
