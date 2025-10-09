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

    def create_task(self, future, command):
        # type: (Any, str) -> str
        """
        Register a new long-running task.

        Args:
            future: asyncio Future object for the task
            command: PFC command string being executed

        Returns:
            str: Unique task ID for tracking
        """
        task_id = str(uuid.uuid4())

        self.tasks[task_id] = {
            "future": future,
            "command": command,
            "start_time": time.time(),
            "status": "running"
        }

        logger.info("✓ Task registered: {} (ID: {})".format(command, task_id))

        return task_id

    def get_task_status(self, task_id):
        # type: (str) -> Dict[str, Any]
        """
        Query task status (non-blocking).

        Args:
            task_id: Task ID to query

        Returns:
            Dict with status information:
                - status: "running", "success", "error", or "not_found"
                - message: Human-readable status message
                - data: Task-specific data
        """
        task_info = self.tasks.get(task_id)

        if not task_info:
            return {
                "status": "not_found",
                "message": "Task ID not found: {}".format(task_id),
                "data": None
            }

        future = task_info["future"]
        command = task_info["command"]
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
                    command, task_id, elapsed_time
                ))

                # Serialize result
                serialized_result = self._serialize_result(result)

                # Build message
                if serialized_result is not None:
                    message = "Task completed: {}\nElapsed time: {:.2f}s\nResult: {}".format(
                        command, elapsed_time, serialized_result
                    )
                else:
                    message = "Task completed: {}\nElapsed time: {:.2f}s".format(
                        command, elapsed_time
                    )

                return {
                    "status": "success",
                    "message": message,
                    "data": serialized_result
                }

            except Exception as e:
                # Task failed
                error_msg = str(e)
                del self.tasks[task_id]

                logger.error("✗ Task failed: {} (ID: {})".format(command, task_id))
                logger.error("  Error: {}".format(error_msg))

                return {
                    "status": "error",
                    "message": "Task failed: {}\nElapsed time: {:.2f}s\nError: {}".format(
                        command, elapsed_time, error_msg
                    ),
                    "data": None
                }

        else:
            # Task still running
            return {
                "status": "running",
                "message": "Task still executing: {}\nElapsed time: {:.2f}s".format(
                    command, elapsed_time
                ),
                "data": {
                    "task_id": task_id,
                    "command": command,
                    "elapsed_time": elapsed_time
                }
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
            command = task_info["command"]
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

            tasks_info.append({
                "task_id": task_id,
                "command": command,
                "status": task_status,
                "elapsed_time": elapsed_time
            })

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
