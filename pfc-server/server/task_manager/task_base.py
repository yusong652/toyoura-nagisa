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

    def __init__(self, task_id, session_id, future, description, task_type, on_status_change=None):
        # type: (str, str, Any, str, str, Any) -> None
        """
        Initialize common task properties.

        Args:
            task_id: Unique task identifier
            session_id: Session identifier for task isolation
            future: asyncio Future object for the task
            description: Human-readable task description
            task_type: Task type identifier ("command" or "script")
            on_status_change: Optional callback function(task) called when task status changes
        """
        self.task_id = task_id
        self.session_id = session_id
        self.future = future
        self.description = description
        self.task_type = task_type
        self.start_time = time.time()
        self.end_time = None  # type: Optional[float]
        self.status = "running"  # type: str
        self.on_status_change = on_status_change  # Callback for persistence

        # Register completion callback
        future.add_done_callback(self._on_complete)

    def _on_complete(self, f):
        # type: (Any) -> None
        """Callback executed when task completes (success or failure)."""
        self.end_time = time.time()
        # Update status based on task result
        try:
            result = f.result(timeout=0)
            # Check result dict status field (for tasks that return error status)
            if isinstance(result, dict) and result.get("status") == "error":
                self.status = "failed"
            else:
                self.status = "completed"
        except Exception:
            self.status = "failed"

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
