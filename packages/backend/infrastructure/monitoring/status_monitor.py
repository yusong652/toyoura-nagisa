"""
Status Monitor - Unified system status tracking coordinator.

This module provides centralized monitoring coordination for all background tasks
and system states that need to be communicated to the LLM via system-reminders.

Architecture:
    StatusMonitor serves as a coordinator, delegating to specialized monitors:
    - InterruptMonitor: User interrupt status
    - QueueMonitor: Queue messages during tool execution
    - BashMonitor: Background bash processes
    - PfcMonitor: PFC simulation tasks
    - TodoMonitor: Todo completion tracking

The monitor is session-scoped and provides unified reminder API.
"""

import logging
from typing import List, Dict, Optional

from .monitors import (
    InterruptMonitor,
    QueueMonitor,
    BashMonitor,
    PfcMonitor,
    TodoMonitor,
)

logger = logging.getLogger(__name__)

# Warning threshold: start warning when remaining iterations <= this value
ITERATION_WARNING_THRESHOLD = 4


class StatusMonitor:
    """
    Unified status monitor coordinator.

    Coordinates monitoring of various background tasks and system states,
    delegating to specialized monitors and aggregating their reminders.

    Design principles:
    - Session-scoped: Each session has its own monitor instance
    - Modular architecture: Each component has its own monitor
    - Unified API: Single entry point for all reminders
    - Async-first: All monitoring methods are async for network calls
    - Explicit parameters: agent_profile passed as method argument, not instance state
    """

    # -------------------------------------------------------------------------
    # Iteration Limit Messages (static, no session state needed)
    # -------------------------------------------------------------------------

    @staticmethod
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

    @staticmethod
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

    def __init__(self, session_id: str):
        """
        Initialize status monitor coordinator for a session.

        Creates all specialized monitors and sets up coordination.

        Args:
            session_id: Session ID for scoped monitoring
        """
        self.session_id = session_id

        # Initialize specialized monitors
        self.interrupt_monitor = InterruptMonitor(session_id)
        self.queue_monitor = QueueMonitor(session_id)
        self.bash_monitor = BashMonitor(session_id)
        self.pfc_monitor = PfcMonitor(session_id)
        self.todo_monitor = TodoMonitor(session_id)

        # Iteration tracking (reset per agent run)
        self._current_iteration: int = 0
        self._max_iterations: int = 0

    # -------------------------------------------------------------------------
    # Iteration Tracking
    # -------------------------------------------------------------------------

    def set_iteration_context(self, current: int, max_iterations: int) -> None:
        """
        Set current iteration context for warning generation.

        Should be called at the start of each agent loop iteration.

        Args:
            current: Current iteration number (0-indexed)
            max_iterations: Maximum allowed iterations
        """
        self._current_iteration = current
        self._max_iterations = max_iterations

    def reset_iteration_context(self) -> None:
        """Reset iteration context when agent run completes."""
        self._current_iteration = 0
        self._max_iterations = 0

    def get_iteration_warning(self) -> Optional[str]:
        """
        Get iteration warning reminder if approaching limit.

        Returns:
            Optional[str]: Warning message if remaining iterations <= threshold, None otherwise
        """
        if self._max_iterations <= 0:
            return None

        remaining = self._max_iterations - self._current_iteration
        if remaining > ITERATION_WARNING_THRESHOLD:
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

    # -------------------------------------------------------------------------
    # Interrupt Monitor Delegation
    # -------------------------------------------------------------------------

    def was_last_response_interrupted(self) -> bool:
        """
        Check if the last response was interrupted by the user.

        Delegates to InterruptMonitor.

        Returns:
            bool: True if last response was interrupted
        """
        return self.interrupt_monitor.was_last_response_interrupted()

    def set_user_interrupted(self) -> None:
        """
        Set the immediate user interrupt flag.

        Delegates to InterruptMonitor.
        """
        self.interrupt_monitor.set_user_interrupted()

    def reset_user_interrupted(self) -> None:
        """
        Reset the immediate user interrupt flag.

        Delegates to InterruptMonitor.
        """
        self.interrupt_monitor.reset_user_interrupted()

    def is_user_interrupted(self) -> bool:
        """
        Check if user has interrupted the current streaming response.

        Delegates to InterruptMonitor.

        Returns:
            bool: True if user pressed ESC to interrupt current response
        """
        return self.interrupt_monitor.is_user_interrupted()

    def set_interrupt_flag(self) -> None:
        """
        Set the persistent interrupt flag in both memory and storage.

        Delegates to InterruptMonitor.
        """
        self.interrupt_monitor.set_interrupt_flag()

    def clear_interrupt_flag(self) -> None:
        """
        Clear the interrupt flag in both memory and persistent storage.

        Delegates to InterruptMonitor.
        """
        self.interrupt_monitor.clear_interrupt_flag()

    # -------------------------------------------------------------------------
    # Main Coordination Method
    # -------------------------------------------------------------------------

    async def get_all_reminders(
        self,
        agent_profile: str = "general",
        check_queue: bool = False
    ) -> List[str]:
        """
        Get all system reminders from monitored sources.

        This is the main entry point called by context managers to collect
        all reminders that should be injected into user messages.

        Args:
            agent_profile: Agent profile type for workspace-dependent monitors.
            check_queue: Whether to check and drain queue messages (during tool recursion)

        Returns:
            List[str]: Combined list of reminder strings from all sources
        """
        reminders = []

        # Set queue checking flag
        self.queue_monitor.check_queue = check_queue

        # Iteration warning (should be first for maximum visibility)
        iteration_warning = self.get_iteration_warning()
        if iteration_warning:
            reminders.append(iteration_warning)

        # Interrupt status
        interrupt_reminders = await self.interrupt_monitor.get_reminders()
        reminders.extend(interrupt_reminders)

        # Queue messages (user messages during tool recursion)
        queue_reminders = await self.queue_monitor.get_reminders()
        reminders.extend(queue_reminders)

        # Bash background processes
        bash_reminders = await self.bash_monitor.get_reminders()
        reminders.extend(bash_reminders)

        # PFC simulation tasks (requires agent_profile)
        pfc_reminders = await self.pfc_monitor.get_reminders(agent_profile)
        reminders.extend(pfc_reminders)

        # Todo reminders (requires agent_profile for workspace resolution)
        todo_reminders = await self.todo_monitor.get_reminders(agent_profile)
        reminders.extend(todo_reminders)

        return reminders


# Singleton registry for session-scoped monitors
_monitor_registry: Dict[str, StatusMonitor] = {}


def get_status_monitor(session_id: str) -> StatusMonitor:
    """
    Get or create a StatusMonitor for a session.

    Maintains singleton pattern per session to preserve state tracking
    across multiple context manager calls.

    Args:
        session_id: Session ID

    Returns:
        StatusMonitor: Session-scoped monitor instance
    """
    if session_id not in _monitor_registry:
        _monitor_registry[session_id] = StatusMonitor(session_id)
    return _monitor_registry[session_id]


def clear_status_monitor(session_id: str) -> None:
    """
    Clear status monitor for a session.

    Should be called when session is deleted or reset.

    Args:
        session_id: Session ID
    """
    if session_id in _monitor_registry:
        del _monitor_registry[session_id]
