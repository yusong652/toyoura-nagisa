"""
Task Manager - Registry and lifecycle management for long-running tasks.

This module provides the main TaskManager class that acts as a registry
for all tracked tasks, delegating type-specific behavior to Task objects.

Python 3.6 compatible implementation.
"""

import uuid
import logging
from typing import Any, Dict, Optional

from .task_base import Task
from .task_types import CommandTask, ScriptTask

# Module logger
logger = logging.getLogger("PFC-Server")


class TaskManager:
    """
    Manage long-running task tracking and status queries.

    This class is separate from PFCCommandExecutor to maintain clear
    separation of concerns: executor executes commands, task manager
    tracks their lifecycle.

    Tasks are represented as polymorphic Task objects (CommandTask, ScriptTask),
    eliminating conditional type checking and enabling clean extension.
    """

    def __init__(self):
        # type: () -> None
        """Initialize task manager with empty task registry."""
        # Task registry: {task_id: Task}
        self.tasks = {}  # type: Dict[str, Task]
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
        task = CommandTask(task_id, future, command)
        self.tasks[task_id] = task
        return task_id

    def create_script_task(self, future, script_name, script_path=None, output_buffer=None, description=None):
        # type: (Any, str, Optional[str], Any, Optional[str]) -> str
        """
        Register a new long-running Python script task.

        Args:
            future: asyncio Future object for the task
            script_name: Name of the script file (e.g., "simulation.py")
            script_path: Optional full path to script for reference
            output_buffer: Optional StringIO buffer for real-time output capture
            description: Task description from PFC agent (LLM-provided)

        Returns:
            str: Unique task ID for tracking
        """
        task_id = uuid.uuid4().hex[:8]
        task = ScriptTask(task_id, future, script_name, script_path, output_buffer, description)
        self.tasks[task_id] = task
        return task_id

    def get_task_status(self, task_id):
        # type: (str) -> Dict[str, Any]
        """
        Query task status (non-blocking).

        Delegates to polymorphic task objects for type-specific handling.

        Args:
            task_id: Task ID to query

        Returns:
            Dict with status information (format depends on task type)
        """
        task = self.tasks.get(task_id)

        if not task:
            return {
                "status": "not_found",
                "message": "Task ID not found: {}".format(task_id),
                "data": None
            }

        return task.get_status_response()

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
        tasks_info = [task.get_task_info() for task in self.tasks.values()]
        message = "Found {} tracked task(s)".format(len(tasks_info))

        return {
            "status": "success",
            "message": message,
            "data": tasks_info
        }

    def cleanup_completed_tasks(self):
        # type: () -> int
        """
        Manually remove completed/failed tasks from tracking.

        By default, completed and failed tasks are kept as historical context.
        Use this method to explicitly clean up old tasks when memory management
        is needed or when the task history becomes too large.

        Returns:
            int: Number of tasks cleaned up
        """
        tasks_to_remove = [
            task_id for task_id, task in self.tasks.items()
            if task.status in ["completed", "failed"]
        ]

        for task_id in tasks_to_remove:
            del self.tasks[task_id]

        if tasks_to_remove:
            logger.info("Cleaned up {} completed task(s)".format(len(tasks_to_remove)))

        return len(tasks_to_remove)
