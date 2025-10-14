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
        task_id = uuid.uuid4().hex[:8]

        self.tasks[task_id] = {
            "future": future,
            "description": command,
            "type": "command",
            "start_time": time.time(),
            "end_time": None,  # Will be set when task completes
            "status": "running"
        }

        # Register callback to capture completion time and status
        def _on_complete(f):
            if task_id in self.tasks:
                self.tasks[task_id]["end_time"] = time.time()
                # Update status based on task result
                try:
                    result = f.result(timeout=0)  # Get task result
                    # Check result dict status field (for commands that return error status)
                    if isinstance(result, dict) and result.get("status") == "error":
                        self.tasks[task_id]["status"] = "failed"
                    else:
                        self.tasks[task_id]["status"] = "completed"
                except Exception:
                    self.tasks[task_id]["status"] = "failed"

        future.add_done_callback(_on_complete)

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
        task_id = uuid.uuid4().hex[:8]

        self.tasks[task_id] = {
            "future": future,
            "description": "script: {}".format(script_name),
            "type": "script",
            "script_name": script_name,
            "script_path": script_path,
            "output_buffer": output_buffer,  # Store buffer reference for live access
            "start_time": time.time(),
            "end_time": None,  # Will be set when task completes
            "status": "running"
        }

        # Register callback to capture completion time and status
        def _on_complete(f):
            if task_id in self.tasks:
                self.tasks[task_id]["end_time"] = time.time()
                # Update status based on task result
                try:
                    result = f.result(timeout=0)  # Get task result
                    # For script tasks, check result dict status field
                    # Script executor returns {"status": "error"} on failure
                    if isinstance(result, dict) and result.get("status") == "error":
                        self.tasks[task_id]["status"] = "failed"
                    else:
                        self.tasks[task_id]["status"] = "completed"
                except Exception:
                    self.tasks[task_id]["status"] = "failed"

        future.add_done_callback(_on_complete)

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
        task_status = task_info["status"]  # Read status from task info (updated by callback)
        start_time = task_info["start_time"]

        # Calculate elapsed time: use end_time if task completed, otherwise current time
        end_time = task_info.get("end_time")
        if end_time is not None:
            elapsed_time = end_time - start_time
        else:
            elapsed_time = time.time() - start_time

        # Check if task is completed or failed (status updated by callback)
        if task_status in ["completed", "failed"]:
            # Task done, retrieve result and remove from tracking
            task_label = "Script" if task_type == "script" else "Command"

            # Get result (should not raise exception as status is already set)
            try:
                result = future.result(timeout=0)
            except Exception as e:
                # Fallback: if future.result() raises, treat as failed
                result = None
                if task_status == "completed":
                    # Unexpected: status says completed but future failed
                    logger.warning("Status mismatch for task {}: status='completed' but future raised: {}".format(
                        task_id, str(e)
                    ))

            # Remove task from tracking
            del self.tasks[task_id]

            # Handle based on task status
            if task_status == "completed":
                # Task completed successfully
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
                    message = "{} completed: {}\nElapsed time: {:.2f}s\nResult: {}".format(
                        task_label, description, elapsed_time, serialized_result
                    )
                else:
                    # No output or result
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
                    response_data["elapsed_time"] = elapsed_time
                else:
                    # For commands, return result data directly
                    response_data = serialized_result if isinstance(serialized_result, dict) else {}
                    if not isinstance(response_data, dict):
                        response_data = {"result": serialized_result}
                    response_data["elapsed_time"] = elapsed_time

                return {
                    "status": result_status,
                    "message": message,
                    "data": response_data
                }

            else:  # task_status == "failed"
                # Task failed
                logger.error("✗ {} task failed: {} (ID: {})".format(task_label, description, task_id))

                # Try to extract error message and partial output (for scripts)
                error_msg = "Task execution failed"
                output_text = None

                if task_type == "script" and isinstance(result, dict):
                    # Script may return partial result with output
                    output_text = result.get("output")
                    error_msg = result.get("message", error_msg)

                # Build error message
                if task_type == "script" and output_text:
                    message = "Script execution failed: {}\nElapsed time: {:.2f}s\nError: {}\n\n=== Partial Output ===\n{}".format(
                        task_info.get("script_name", description), elapsed_time, error_msg, output_text
                    )
                    error_data = {"error": error_msg, "output": output_text, "elapsed_time": elapsed_time}
                else:
                    message = "{} failed: {}\nElapsed time: {:.2f}s\nError: {}".format(
                        task_label, description, elapsed_time, error_msg
                    )
                    error_data = {"error": error_msg, "elapsed_time": elapsed_time}

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
            description = task_info["description"]
            task_type = task_info.get("type", "command")
            task_status = task_info["status"]  # Read status directly (updated by callback)
            start_time = task_info["start_time"]
            elapsed_time = time.time() - start_time

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
            task_status = task_info["status"]
            if task_status in ["completed", "failed"]:
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
