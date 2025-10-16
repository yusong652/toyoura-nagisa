"""
Task Manager - Registry and lifecycle management for long-running tasks.

This module provides the main TaskManager class that acts as a registry
for all tracked tasks, delegating type-specific behavior to Task objects.

Python 3.6 compatible implementation.
"""

import uuid
import logging
from typing import Any, Dict, Optional, List

from .task_base import Task
from .task_types import CommandTask, ScriptTask
from .persistence import TaskPersistence

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

    def __init__(self, enable_persistence=True):
        # type: (bool,) -> None
        """
        Initialize task manager with empty task registry.

        Args:
            enable_persistence: Enable task persistence to disk (default: True)
        """
        # Task registry: {task_id: Task}
        self.tasks = {}  # type: Dict[str, Task]

        # Persistence manager
        self.enable_persistence = enable_persistence
        if enable_persistence:
            self.persistence = TaskPersistence()
            # Load historical tasks from disk
            self._load_historical_tasks()
        else:
            self.persistence = None

        logger.info("✓ TaskManager initialized (persistence: {})".format(
            "enabled" if enable_persistence else "disabled"
        ))

    def _load_historical_tasks(self):
        # type: () -> None
        """Load historical tasks from disk on startup."""
        if not self.persistence:
            return

        try:
            tasks_data = self.persistence.load_tasks()
            for task_data in tasks_data:
                historical_task = self.persistence.restore_task_as_historical(task_data)
                if historical_task:
                    self.tasks[historical_task.task_id] = historical_task

            logger.info("✓ Loaded {} historical task(s)".format(len(tasks_data)))
        except Exception as e:
            logger.error("Failed to load historical tasks: {}".format(e))

    def create_command_task(self, session_id, future, command):
        # type: (str, Any, str) -> str
        """
        Register a new long-running PFC command task.

        Args:
            session_id: Session identifier for task isolation
            future: asyncio Future object for the task
            command: PFC command string being executed

        Returns:
            str: Unique task ID for tracking
        """
        task_id = uuid.uuid4().hex[:8]
        # Pass save callback for automatic persistence on status change
        task = CommandTask(task_id, session_id, future, command, on_status_change=self._on_task_status_change)
        self.tasks[task_id] = task

        # Save to disk immediately
        self._save_tasks()

        return task_id

    def create_script_task(self, session_id, future, script_name, script_path=None, output_buffer=None, description=None):
        # type: (str, Any, str, Optional[str], Any, Optional[str]) -> str
        """
        Register a new long-running Python script task.

        Args:
            session_id: Session identifier for task isolation
            future: asyncio Future object for the task
            script_name: Name of the script file (e.g., "simulation.py")
            script_path: Optional full path to script for reference
            output_buffer: Optional StringIO buffer for real-time output capture
            description: Task description from PFC agent (LLM-provided)

        Returns:
            str: Unique task ID for tracking
        """
        task_id = uuid.uuid4().hex[:8]
        # Pass save callback for automatic persistence on status change
        task = ScriptTask(
            task_id, session_id, future, script_name, script_path,
            output_buffer, description, on_status_change=self._on_task_status_change
        )
        self.tasks[task_id] = task

        # Save to disk immediately
        self._save_tasks()

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

    def list_all_tasks(self, session_id=None):
        # type: (Optional[str]) -> Dict[str, Any]
        """
        List currently tracked tasks, optionally filtered by session.

        Args:
            session_id: Optional session ID to filter tasks

        Returns:
            Dict with task list:
                - status: "success"
                - message: Summary message
                - data: List of task info dictionaries
        """
        # Filter tasks by session if specified
        if session_id:
            filtered_tasks = [
                task for task in self.tasks.values()
                if task.session_id == session_id
            ]
            tasks_info = [task.get_task_info() for task in filtered_tasks]
            message = "Found {} tracked task(s) for session {}".format(
                len(tasks_info), session_id
            )
        else:
            tasks_info = [task.get_task_info() for task in self.tasks.values()]
            message = "Found {} tracked task(s) across all sessions".format(len(tasks_info))

        return {
            "status": "success",
            "message": message,
            "data": tasks_info
        }

    def cleanup_completed_tasks(self, session_id=None):
        # type: (Optional[str]) -> int
        """
        Manually remove completed/failed tasks from tracking.

        By default, completed and failed tasks are kept as historical context.
        Use this method to explicitly clean up old tasks when memory management
        is needed or when the task history becomes too large.

        Args:
            session_id: Optional session ID to clean up. If None, cleans all sessions.

        Returns:
            int: Number of tasks cleaned up
        """
        if session_id:
            # Clean up specific session
            tasks_to_remove = [
                task_id for task_id, task in self.tasks.items()
                if task.session_id == session_id and task.status in ["completed", "failed"]
            ]
        else:
            # Clean up all sessions
            tasks_to_remove = [
                task_id for task_id, task in self.tasks.items()
                if task.status in ["completed", "failed"]
            ]

        for task_id in tasks_to_remove:
            del self.tasks[task_id]

        if tasks_to_remove:
            logger.info("Cleaned up {} completed task(s) {}".format(
                len(tasks_to_remove),
                "for session {}".format(session_id) if session_id else "across all sessions"
            ))
            # Save changes to disk
            self._save_tasks()

        return len(tasks_to_remove)

    def _save_tasks(self):
        # type: () -> None
        """Save current tasks to disk (if persistence enabled)."""
        if self.persistence:
            # Save asynchronously to avoid blocking
            self.persistence.save_tasks(self.tasks)

    def _on_task_status_change(self, task):
        # type: (Task) -> None
        """
        Callback invoked when a task's status changes (completion/failure).

        Automatically saves task state to disk for persistence.

        Args:
            task: Task that changed status
        """
        logger.debug("Task {} status changed to: {}".format(task.task_id, task.status))
        # Save tasks to disk
        self._save_tasks()
