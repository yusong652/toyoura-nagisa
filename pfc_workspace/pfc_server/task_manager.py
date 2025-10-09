"""
PFC Task Manager - Manages long-running task tracking and status.

This module provides task lifecycle management separate from command execution.
Status queries do not go through the executor as they are not PFC commands.

Python 3.6 compatible implementation.
"""

import time
import uuid
import logging
from typing import Any, Dict, Optional

# Module logger
logger = logging.getLogger("PFC-Server")


class TaskManager:
    """
    Manage long-running task tracking and status queries.

    This class is separate from PFCCommandExecutor to maintain clear
    separation of concerns: executor executes commands, task manager
    tracks their lifecycle.
    """

    def __init__(self):
        # type: () -> None
        """Initialize task manager with empty task registry."""
        # Task registry: {task_id: TaskInfo}
        self.tasks = {}  # type: Dict[str, Dict[str, Any]]
        logger.info("✓ TaskManager initialized")

    def create_command_task(self, future, command):
        # type: (Any, str) -> str
        """
        Register a new long-running PFC command task.

        Args:
            future: asyncio Future object for the task
            command: PFC command string being executed

        Returns:
            str: Unique task ID for tracking
        """
        task_id = str(uuid.uuid4())

        self.tasks[task_id] = {
            "future": future,
            "description": command,
            "type": "command",
            "start_time": time.time(),
            "status": "running"
        }

        logger.info("✓ Command task registered: {} (ID: {})".format(command, task_id))

        return task_id

    def create_script_task(self, future, script_name, script_path=None, output_buffer=None):
        # type: (Any, str, Optional[str], Any) -> str
        """
        Register a new long-running Python script task.

        Args:
            future: asyncio Future object for the task
            script_name: Name of the script file (e.g., "simulation.py")
            script_path: Optional full path to script for reference
            output_buffer: Optional StringIO buffer for real-time output capture

        Returns:
            str: Unique task ID for tracking
        """
        task_id = str(uuid.uuid4())

        self.tasks[task_id] = {
            "future": future,
            "description": "script: {}".format(script_name),
            "type": "script",
            "script_name": script_name,
            "script_path": script_path,
            "output_buffer": output_buffer,  # Store buffer reference for live access
            "start_time": time.time(),
            "status": "running"
        }

        logger.info("✓ Script task registered: {} (ID: {})".format(script_name, task_id))

        return task_id

    def get_task_status(self, task_id):
        # type: (str) -> Dict[str, Any]
        """
        Query task status (non-blocking).

        Handles both command and script tasks appropriately:
        - Command tasks: Return result data only
        - Script tasks: Extract and return output + result data

        Args:
            task_id: Task ID to query

        Returns:
            Dict with status information:
                - status: "running", "success", "error", or "not_found"
                - message: Human-readable status message
                - data: Task-specific data (includes output for scripts)
        """
        task_info = self.tasks.get(task_id)

        if not task_info:
            return {
                "status": "not_found",
                "message": "Task ID not found: {}".format(task_id),
                "data": None
            }

        future = task_info["future"]
        description = task_info["description"]
        task_type = task_info.get("type", "command")  # Default to command for backward compatibility
        start_time = task_info["start_time"]
        elapsed_time = time.time() - start_time

        # Check if task is done (non-blocking)
        if future.done():
            # Task completed, get result
            try:
                result = future.result(timeout=0)  # Non-blocking

                # Mark as completed and remove from active tasks
                del self.tasks[task_id]

                logger.info("✓ Task completed: {} (ID: {}, Time: {:.2f}s)".format(
                    description, task_id, elapsed_time
                ))

                # Extract output and data based on task type
                output_text = None
                result_data = None
                result_status = "success"

                if task_type == "script":
                    # Script execution result - extract output and data
                    if isinstance(result, dict):
                        output_text = result.get("output")
                        result_data = result.get("data")
                        result_status = result.get("status", "success")
                    else:
                        result_data = result
                else:
                    # Command execution result - direct value
                    result_data = result

                # Serialize result data
                serialized_result = self._serialize_result(result_data)

                # Build message based on task type
                if task_type == "script" and output_text:
                    # Script with captured output
                    message = "Script execution completed: {}\nElapsed time: {:.2f}s\n\n=== Script Output ===\n{}".format(
                        task_info.get("script_name", description), elapsed_time, output_text
                    )
                elif serialized_result is not None:
                    # Command with return value or script with data
                    task_label = "Script" if task_type == "script" else "Command"
                    message = "{} completed: {}\nElapsed time: {:.2f}s\nResult: {}".format(
                        task_label, description, elapsed_time, serialized_result
                    )
                else:
                    # No output or result
                    task_label = "Script" if task_type == "script" else "Command"
                    message = "{} completed: {}\nElapsed time: {:.2f}s".format(
                        task_label, description, elapsed_time
                    )

                # Build response data
                if task_type == "script":
                    # For scripts, always include output field
                    response_data = serialized_result if isinstance(serialized_result, dict) else {}
                    if not isinstance(response_data, dict):
                        response_data = {"result": serialized_result}
                    response_data["output"] = output_text if output_text else ""
                else:
                    # For commands, return result data directly
                    response_data = serialized_result

                return {
                    "status": result_status,
                    "message": message,
                    "data": response_data
                }

            except Exception as e:
                # Task failed - but might have partial output (for scripts)
                error_msg = str(e)

                # Try to get partial result with output (for scripts)
                output_text = None
                if task_type == "script":
                    try:
                        partial_result = future.result(timeout=0)
                        if isinstance(partial_result, dict):
                            output_text = partial_result.get("output")
                    except Exception:
                        pass

                del self.tasks[task_id]

                task_label = "Script" if task_type == "script" else "Command"
                logger.error("✗ {} task failed: {} (ID: {})".format(task_label, description, task_id))
                logger.error("  Error: {}".format(error_msg))

                # Build error message with output if available (scripts only)
                if task_type == "script" and output_text:
                    message = "Script execution failed: {}\nElapsed time: {:.2f}s\nError: {}\n\n=== Partial Output ===\n{}".format(
                        task_info.get("script_name", description), elapsed_time, error_msg, output_text
                    )
                    error_data = {"error": error_msg, "output": output_text}
                else:
                    message = "{} failed: {}\nElapsed time: {:.2f}s\nError: {}".format(
                        task_label, description, elapsed_time, error_msg
                    )
                    error_data = {"error": error_msg}

                return {
                    "status": "error",
                    "message": message,
                    "data": error_data
                }

        else:
            # Task still running
            task_label = "Script" if task_type == "script" else "Command"

            # For script tasks, get current output from buffer if available
            current_output = None
            if task_type == "script":
                output_buffer = task_info.get("output_buffer")
                if output_buffer:
                    try:
                        # Read current buffer content (thread-safe operation)
                        current_output = output_buffer.getvalue()
                    except Exception as e:
                        logger.warning("Failed to read output buffer: {}".format(e))

            response_data = {
                "task_id": task_id,
                "task_type": task_type,
                "description": description,
                "elapsed_time": elapsed_time
            }

            # Include current output for scripts
            if current_output:
                response_data["output"] = current_output

            return {
                "status": "running",
                "message": "{} still executing: {}\nElapsed time: {:.2f}s".format(
                    task_label, description, elapsed_time
                ),
                "data": response_data
            }

    def list_all_tasks(self):
        # type: () -> Dict[str, Any]
        """
        List all currently tracked tasks.

        Returns:
            Dict with task list:
                - status: "success"
                - message: Summary message
                - data: List of task info dictionaries
        """
        tasks_info = []

        for task_id, task_info in self.tasks.items():
            future = task_info["future"]
            description = task_info["description"]
            task_type = task_info.get("type", "command")
            start_time = task_info["start_time"]
            elapsed_time = time.time() - start_time

            # Check if done (non-blocking)
            if future.done():
                try:
                    future.result(timeout=0)
                    task_status = "completed"
                except Exception:
                    task_status = "failed"
            else:
                task_status = "running"

            task_entry = {
                "task_id": task_id,
                "task_type": task_type,
                "description": description,
                "status": task_status,
                "elapsed_time": elapsed_time
            }

            # Add script-specific info if applicable
            if task_type == "script":
                task_entry["script_name"] = task_info.get("script_name")

            tasks_info.append(task_entry)

        message = "Found {} tracked task(s)".format(len(tasks_info))

        return {
            "status": "success",
            "message": message,
            "data": tasks_info
        }

    def cleanup_completed_tasks(self):
        # type: () -> int
        """
        Remove completed/failed tasks from tracking.

        Returns:
            int: Number of tasks cleaned up
        """
        tasks_to_remove = []

        for task_id, task_info in self.tasks.items():
            future = task_info["future"]
            if future.done():
                tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del self.tasks[task_id]

        if tasks_to_remove:
            logger.info("Cleaned up {} completed task(s)".format(len(tasks_to_remove)))

        return len(tasks_to_remove)

    def _serialize_result(self, result):
        # type: (Any) -> Any
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
