"""
User PFC Python Monitor - User PFC Python command context injection.

Stores user PFC Python command outputs and injects them into LLM context
following Claude Code's pattern for intent awareness.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)

# Context message for LLM awareness of user PFC operations
CONTEXT_MESSAGE = """The user executed the following PFC Python commands in the console.
These commands have modified the simulation state. Be aware of these operations when assisting the user."""


@dataclass
class PfcPythonContext:
    """Single PFC Python command context."""
    code: str
    task_id: str
    output: str
    error: Optional[str] = None


class UserPfcPythonMonitor(BaseMonitor):
    """
    Monitor for user PFC Python command context injection.

    Stores user-executed PFC Python commands (> prefix) and their outputs,
    injecting them into LLM context so the AI can "see" user operations.

    Design follows Claude Code's pattern:
    - User operations are visible to LLM (intent awareness)
    - Default: don't respond to PFC output (reduce noise)
    - User can explicitly ask about the output (flexibility)
    """

    def __init__(self, session_id: str):
        """
        Initialize user PFC Python monitor.

        Args:
            session_id: Session ID for scoped monitoring
        """
        super().__init__(session_id)
        self._contexts: List[PfcPythonContext] = []

    def add_context(
        self,
        code: str,
        task_id: str,
        output: str,
        error: Optional[str] = None
    ) -> None:
        """
        Add a PFC Python command context for injection.

        Args:
            code: The Python code executed
            task_id: Task ID assigned to the execution
            output: Captured stdout from execution
            error: Error message if execution failed
        """
        self._contexts.append(PfcPythonContext(
            code=code,
            task_id=task_id,
            output=output,
            error=error,
        ))
        logger.debug(f"Added PFC Python context for task: {task_id}")

    def clear_contexts(self) -> None:
        """Clear all stored contexts."""
        self._contexts.clear()

    def has_contexts(self) -> bool:
        """Check if there are any pending contexts."""
        return len(self._contexts) > 0

    def _format_context(self, ctx: PfcPythonContext) -> str:
        """
        Format a single PFC Python context.

        Args:
            ctx: The PFC Python context to format

        Returns:
            Formatted string with pfc-python tags
        """
        return (
            f"<pfc-python>\n"
            f"<input>{ctx.code}</input>\n"
            f"<task_id>{ctx.task_id}</task_id>\n"
            f"<output>{ctx.output}</output>\n"
            f"<error>{ctx.error if ctx.error else ''}</error>\n"
            f"</pfc-python>"
        )

    async def get_reminders(self) -> List[str]:
        """
        Get user PFC Python contexts as reminder blocks.

        Contexts are consumed (cleared) after retrieval to prevent
        duplicate injection.

        Returns:
            List[str]: Formatted system-reminder blocks
        """
        if not self._contexts:
            return []

        # Format all contexts
        formatted_contexts = [
            self._format_context(ctx) for ctx in self._contexts
        ]

        # Combine with context message
        combined = CONTEXT_MESSAGE + "\n\n" + "\n\n".join(formatted_contexts)

        # Wrap in system-reminder block
        reminder_block = f"<system-reminder>\n{combined}\n</system-reminder>"

        # Clear contexts after retrieval (consume once)
        context_count = len(self._contexts)
        self._contexts.clear()

        logger.info(f"Injected {context_count} user PFC Python context(s)")

        return [reminder_block]


# Registry for session-scoped monitors (separate from StatusMonitor registry)
_user_pfc_python_monitors: dict[str, UserPfcPythonMonitor] = {}


def get_user_pfc_python_monitor(session_id: str) -> UserPfcPythonMonitor:
    """
    Get or create a UserPfcPythonMonitor for a session.

    This function allows PFC Console API to access the monitor directly
    for adding contexts without going through StatusMonitor.

    Args:
        session_id: Session ID

    Returns:
        UserPfcPythonMonitor: Session-scoped monitor instance
    """
    if session_id not in _user_pfc_python_monitors:
        _user_pfc_python_monitors[session_id] = UserPfcPythonMonitor(session_id)
    return _user_pfc_python_monitors[session_id]


def clear_user_pfc_python_monitor(session_id: str) -> None:
    """
    Clear user PFC Python monitor for a session.

    Should be called when session is deleted.

    Args:
        session_id: Session ID
    """
    if session_id in _user_pfc_python_monitors:
        del _user_pfc_python_monitors[session_id]
