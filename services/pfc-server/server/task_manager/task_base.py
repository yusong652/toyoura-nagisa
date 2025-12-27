"""
Task Base Classes - Abstract base class for all task types.

This module defines the common interface and lifecycle management
for all task types in the PFC task manager.

Python 3.6 compatible implementation.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# Module logger
logger = logging.getLogger("PFC-Server")


class Task(ABC):
    """
    Abstract base class for all task types.

    Defines common task lifecycle and status tracking, with subclasses
    implementing type-specific behavior (e.g., output capture for scripts).
    """

    def __init__(self, task_id, session_id, future, description, task_type="script", on_status_change=None):
        # type: (str, str, Any, str, str, Any) -> None
        """
        Initialize common task properties.

        Args:
            task_id: Unique task identifier
            session_id: Session identifier for task isolation
            future: asyncio Future object for the task
            description: Human-readable task description
            task_type: Task type identifier (default: "script")
            on_status_change: Optional callback function(task) called when task status changes
        """
        self.task_id = task_id
        self.session_id = session_id
        self.future = future
        self.description = description
        self.task_type = task_type
        self.start_time = time.time()
        self.end_time = None  # type: Optional[float]
        self._status = "pending"  # type: str  # Internal status, use get_status() for current state
        self.notified = False  # type: bool  # Whether completion has been notified to LLM
        self.on_status_change = on_status_change  # Callback for persistence
        self.error = None  # type: Optional[str]  # Error message (extracted on completion)

        # Register completion callback
        future.add_done_callback(self._on_complete)

    @property
    def status(self):
        # type: () -> str
        """
        Get current task status by checking future state.

        Status values:
        - "pending": Task queued, waiting for main thread
        - "running": Task currently executing in main thread
        - "completed": Task finished successfully
        - "failed": Task finished with error
        - "interrupted": Task was interrupted by user
        """
        # If already completed, return stored status
        if self._status in ("completed", "failed", "interrupted"):
            return self._status

        # Check future state for pending/running tasks
        if self.future.done():
            # Future completed but status not yet updated (race condition)
            return self._status
        elif self.future.running():
            return "running"
        else:
            return "pending"

    @status.setter
    def status(self, value):
        # type: (str) -> None
        """Set task status (used by _on_complete callback)."""
        self._status = value

    def _on_complete(self, f):
        # type: (Any) -> None
        """Callback executed when task completes (success, failure, or interruption)."""
        self.end_time = time.time()
        # Update status based on task result
        try:
            result = f.result(timeout=0)
            # Check result dict status field (for tasks that return error/interrupted status)
            if isinstance(result, dict):
                result_status = result.get("status")
                if result_status == "error":
                    self.status = "failed"
                    # Extract error message for persistence
                    self.error = result.get("message", "Task execution failed")
                elif result_status == "interrupted":
                    self.status = "interrupted"
                else:
                    self.status = "completed"
            else:
                self.status = "completed"
        except Exception as e:
            self.status = "failed"
            self.error = str(e)

        # Notify status change for persistence
        if self.on_status_change:
            try:
                self.on_status_change(self)
            except Exception as e:
                logger.warning("Status change callback failed: {}".format(e))

    def get_elapsed_time(self):
        # type: () -> float
        """Calculate elapsed time since task start."""
        if self.end_time is not None:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @abstractmethod
    def get_status_response(self):
        # type: () -> Dict[str, Any]
        """
        Get task status response (implemented by subclasses).

        Returns:
            Dict with status, message, and data fields
        """
        pass

    @abstractmethod
    def get_task_info(self):
        # type: () -> Dict[str, Any]
        """
        Get task info for listing (implemented by subclasses).

        Returns:
            Dict with task summary information
        """
        pass

    @staticmethod
    def _serialize_result(result):
        # type: (Any) -> Any
        """Convert PFC objects to JSON-serializable format."""
        if result is None:
            return None
        elif isinstance(result, (str, int, float, bool)):
            return result
        elif isinstance(result, (list, tuple)):
            return [Task._serialize_result(item) for item in result]
        elif isinstance(result, dict):
            return {k: Task._serialize_result(v) for k, v in result.items()}
        else:
            # For complex PFC objects, return string representation
            return str(result)
