"""
User PFC Task Monitor - User PFC task status context injection.

Stores user PFC task status queries and injects them into LLM context
for intent awareness when user checks task details via /pfc-list-tasks.

Uses shared task_status_formatter for consistent output format.
"""

import logging
from typing import List, Optional
from .base_monitor import BaseMonitor
from backend.application.tools.pfc.utils import (
    TaskStatusData,
    format_task_status_for_context,
)

logger = logging.getLogger(__name__)

# Context message for LLM awareness of user task queries
CONTEXT_MESSAGE = """The user just checked the status of a PFC task.
This indicates they want to know about this task's progress or results."""


class UserPfcTaskMonitor(BaseMonitor):
    """
    Monitor for user PFC task status context injection.

    Stores user task status queries (from /pfc-list-tasks command) and injects
    them into LLM context so the AI can understand user's current focus.

    Design follows Claude Code's pattern:
    - User operations are visible to LLM (intent awareness)
    - Context is consumed after one use (avoid stale info)
    """

    def __init__(self, session_id: str):
        """
        Initialize user PFC task monitor.

        Args:
            session_id: Session ID for scoped monitoring
        """
        super().__init__(session_id)
        self._context: Optional[TaskStatusData] = None

    def add_context(
        self,
        task_id: str,
        status: str,
        entry_script: Optional[str] = None,
        description: Optional[str] = None,
        output: Optional[str] = None,
        error: Optional[str] = None,
        elapsed_time: Optional[float] = None,
        git_commit: Optional[str] = None,
    ) -> None:
        """
        Add a PFC task status context for injection.

        Only keeps the most recent query (replaces previous).

        Args:
            task_id: Task ID queried
            status: Task status (running, completed, failed, etc.)
            entry_script: Entry script path
            description: Task description
            output: Task output
            error: Error message if task failed
            elapsed_time: Execution time in seconds
            git_commit: Git commit hash for version tracking
        """
        self._context = TaskStatusData(
            task_id=task_id,
            status=status,
            entry_script=entry_script,
            description=description,
            output=output,
            error=error,
            elapsed_time=elapsed_time,
            git_commit=git_commit,
        )
        logger.debug(f"Added PFC task context for task: {task_id}")

    def clear_context(self) -> None:
        """Clear stored context."""
        self._context = None

    def has_context(self) -> bool:
        """Check if there is a pending context."""
        return self._context is not None

    async def get_reminders(self) -> List[str]:
        """
        Get user PFC task context as reminder block.

        Context is consumed (cleared) after retrieval to prevent
        duplicate injection.

        Returns:
            List[str]: Formatted system-reminder blocks
        """
        if not self._context:
            return []

        # Format context using shared formatter
        formatted = format_task_status_for_context(self._context)

        # Combine with context message
        combined = CONTEXT_MESSAGE + "\n\n" + formatted

        # Wrap in system-reminder block
        reminder_block = f"<system-reminder>\n{combined}\n</system-reminder>"

        # Clear context after retrieval (consume once)
        task_id = self._context.task_id
        self._context = None

        logger.info(f"Injected user PFC task context for: {task_id}")

        return [reminder_block]


# Registry for session-scoped monitors
_user_pfc_task_monitors: dict[str, UserPfcTaskMonitor] = {}


def get_user_pfc_task_monitor(session_id: str) -> UserPfcTaskMonitor:
    """
    Get or create a UserPfcTaskMonitor for a session.

    Args:
        session_id: Session ID

    Returns:
        UserPfcTaskMonitor: Session-scoped monitor instance
    """
    if session_id not in _user_pfc_task_monitors:
        _user_pfc_task_monitors[session_id] = UserPfcTaskMonitor(session_id)
    return _user_pfc_task_monitors[session_id]


def clear_user_pfc_task_monitor(session_id: str) -> None:
    """
    Clear user PFC task monitor for a session.

    Args:
        session_id: Session ID
    """
    if session_id in _user_pfc_task_monitors:
        del _user_pfc_task_monitors[session_id]
