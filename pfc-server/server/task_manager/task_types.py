"""
Task Type Implementations - Script execution task class.

This module contains ScriptTask implementation, providing type-specific
behavior for Python script execution with real-time output capture.

Python 3.6 compatible implementation.
"""

import logging
from typing import Any, Dict, Optional

from .task_base import Task

# Module logger
logger = logging.getLogger("PFC-Server")


class ScriptTask(Task):
    """
    Task for Python script execution.

    Enhanced task type with real-time output capture via StringIO buffer,
    suitable for long-running simulations with progress monitoring.
    """

    def __init__(self, task_id, session_id, future, script_name, script_path=None, output_buffer=None, description=None, on_status_change=None):
        # type: (str, str, Any, str, Optional[str], Any, Optional[str], Any) -> None
        """
        Initialize script task.

        Args:
            task_id: Unique task identifier
            session_id: Session identifier for task isolation
            future: asyncio Future object for the task
            script_name: Name of the script file (e.g., "simulation.py")
            script_path: Optional full path to script for reference
            output_buffer: Optional StringIO buffer for real-time output capture
            description: Task description from PFC agent (LLM-provided)
            on_status_change: Optional callback function(task) called when task status changes
        """
        # Use agent-provided description directly
        super(ScriptTask, self).__init__(task_id, session_id, future, description, "script", on_status_change)
        self.script_name = script_name
        self.script_path = script_path
        self.output_buffer = output_buffer

        logger.info("✓ Script task registered: {} (ID: {}, Session: {})".format(
            script_name, task_id, session_id
        ))

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
                "session_id": self.session_id,
                "task_type": self.task_type,
                "script_name": self.script_name,
                "script_path": self.script_path,
                "description": self.description,
                "start_time": self.start_time,
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

            # Build unified response data with all metadata
            response_data = {
                "task_id": self.task_id,
                "session_id": self.session_id,
                "task_type": self.task_type,
                "script_name": self.script_name,
                "script_path": self.script_path,
                "description": self.description,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "elapsed_time": elapsed_time,
                "output": output_text if output_text else "",
                "result": serialized_result  # Script's 'result' variable
            }

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
            else:
                message = "Script failed: {}\nElapsed time: {:.2f}s\nError: {}".format(
                    self.description, elapsed_time, error_msg
                )

            # Build unified error data with all metadata
            error_data = {
                "task_id": self.task_id,
                "session_id": self.session_id,
                "task_type": self.task_type,
                "script_name": self.script_name,
                "script_path": self.script_path,
                "description": self.description,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "elapsed_time": elapsed_time,
                "output": output_text if output_text else "",
                "error": error_msg
            }

            return {
                "status": "error",
                "message": message,
                "data": error_data
            }

    def get_task_info(self):
        # type: () -> Dict[str, Any]
        """Get script task summary for listing."""
        info = {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "task_type": self.task_type,
            "description": self.description,  # Agent-provided task description
            "status": self.status,
            "elapsed_time": self.get_elapsed_time(),
            "start_time": self.start_time,
            "name": self.script_name,  # Script file name (for backward compatibility)
            "script_path": self.script_path  # Absolute path for LLM
        }
        # Add end_time for completed/failed tasks
        if self.status in ["completed", "failed"] and self.end_time is not None:
            info["end_time"] = self.end_time
        return info
