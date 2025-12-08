"""
Iteration Monitor - Agent loop iteration tracking.

Provides proactive warnings to LLM when approaching iteration limit,
allowing natural task completion instead of abrupt termination.
"""

import logging
from typing import List, Optional
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)

# Warning threshold: start warning when remaining iterations <= this value
WARNING_THRESHOLD = 4


class IterationMonitor(BaseMonitor):
    """
    Monitor for agent loop iteration tracking.

    Tracks current iteration and max_iterations to generate
    proactive warnings when approaching the limit.

    Note: This monitor is reset per agent run, not per session.
    """

    def __init__(self, session_id: str):
        """
        Initialize iteration monitor.

        Args:
            session_id: Session ID for scoped monitoring
        """
        super().__init__(session_id)
        self._current_iteration: int = 0
        self._max_iterations: int = 0

    def set_context(self, current: int, max_iterations: int) -> None:
        """
        Set current iteration context for warning generation.

        Should be called at the start of each agent loop iteration.

        Args:
            current: Current iteration number (0-indexed)
            max_iterations: Maximum allowed iterations
        """
        self._current_iteration = current
        self._max_iterations = max_iterations

    def reset(self) -> None:
        """Reset iteration context when agent run completes."""
        self._current_iteration = 0
        self._max_iterations = 0

    def get_warning(self) -> Optional[str]:
        """
        Get iteration warning message if approaching limit.

        Returns:
            Optional[str]: Warning message if remaining iterations <= threshold,
                          None otherwise
        """
        if self._max_iterations <= 0:
            return None

        remaining = self._max_iterations - self._current_iteration
        if remaining > WARNING_THRESHOLD:
            return None

        if remaining <= 1:
            return (
                f"URGENT: This is your LAST iteration (iteration {self._current_iteration + 1}/{self._max_iterations}). "
                f"You MUST provide a final summary NOW. Do NOT call any more tools."
            )
        elif remaining <= 2:
            return (
                f"WARNING: Only {remaining} iterations remaining ({self._current_iteration + 1}/{self._max_iterations}). "
                f"Please wrap up your current task and prepare to summarize your findings."
            )
        else:
            return (
                f"Note: {remaining} iterations remaining ({self._current_iteration + 1}/{self._max_iterations}). "
                f"Consider planning your remaining steps carefully."
            )

    async def get_reminders(self) -> List[str]:
        """
        Get iteration warning as system reminder.

        Returns:
            List[str]: Warning reminder block if approaching limit, empty list otherwise
        """
        warning = self.get_warning()
        if not warning:
            return []

        reminder_block = f"<system-reminder>\n{warning}\n</system-reminder>"
        return [reminder_block]


# Static utility methods for iteration limit messages
# (used when limit is actually reached, not just warnings)

def get_iteration_limit_tool_message(max_iterations: int) -> str:
    """
    Get the message to inject as tool result when iteration limit is reached.

    Used by MainAgent to inform LLM that tool execution was stopped.

    Args:
        max_iterations: The iteration limit that was reached

    Returns:
        str: Message to inject as tool result content
    """
    return (
        f"Tool execution stopped: Reached iteration limit "
        f"({max_iterations} iterations).\n\n"
        f"The task may be incomplete. You can provide a summary of what was accomplished.\n\n"
        f"Note: This is a safety mechanism to prevent infinite loops."
    )


def get_iteration_limit_summary_instruction() -> str:
    """
    Get the instruction to request summary when SubAgent reaches iteration limit.

    Used by SubAgent to ask LLM for a final summary after executing pending tools.

    Returns:
        str: Instruction to inject as user message
    """
    return (
        "You have reached the iteration limit. Based on all the tool results above, "
        "please provide a comprehensive summary of your findings. "
        "Do NOT call any more tools - just summarize what you found."
    )
