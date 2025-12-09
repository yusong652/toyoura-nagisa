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
from typing import List, Dict

from .monitors import (
    InterruptMonitor,
    QueueMonitor,
    BashMonitor,
    PfcMonitor,
    TodoMonitor,
    IterationMonitor,
)
from .monitors.iteration_monitor import get_iteration_limit_tool_message

logger = logging.getLogger(__name__)


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

    # Re-export iteration limit message function for backward compatibility
    get_iteration_limit_tool_message = staticmethod(get_iteration_limit_tool_message)

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
        self.iteration_monitor = IterationMonitor(session_id)

    # -------------------------------------------------------------------------
    # Iteration Monitor Delegation
    # -------------------------------------------------------------------------

    def set_iteration_context(self, current: int, max_iterations: int) -> None:
        """
        Set current iteration context for warning generation.

        Delegates to IterationMonitor.

        Args:
            current: Current iteration number (0-indexed)
            max_iterations: Maximum allowed iterations
        """
        self.iteration_monitor.set_context(current, max_iterations)

    def reset_iteration_context(self) -> None:
        """
        Reset iteration context when agent run completes.

        Delegates to IterationMonitor.
        """
        self.iteration_monitor.reset()

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
        iteration_reminders = await self.iteration_monitor.get_reminders()
        reminders.extend(iteration_reminders)

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
