"""
Status Monitor - Unified system status tracking for reminders

This module provides centralized monitoring for all background tasks and system states
that need to be communicated to the LLM via system-reminders:

1. Bash background processes
2. PFC simulation tasks (TODO)
3. User interrupt status (TODO)
4. Task queue status (TODO)

The monitor is session-scoped and maintains state for status transition detection.
"""

from typing import List, Dict, Set


class StatusMonitor:
    """
    Unified status monitor for all system reminders.

    Coordinates monitoring of various background tasks and system states,
    providing formatted reminder strings for injection into LLM context.

    Design principles:
    - Session-scoped: Each session has its own monitor instance
    - Incremental implementation: Start with bash, add features gradually
    - State tracking: Detects transitions (e.g., task completion)
    - Async-first: All monitoring methods are async for network calls
    """

    def __init__(self, session_id: str):
        """
        Initialize status monitor for a session.

        Args:
            session_id: Session ID for scoped monitoring
        """
        self.session_id = session_id

        # TODO: PFC task state tracking (to be added after bash testing)
        # self._pfc_notified_completions: Set[str] = set()
        # self._pfc_last_task_states: Dict[str, str] = {}

        # TODO: User interrupt state (to be added after PFC)
        # self._last_response_interrupted: bool = False

        # TODO: Queue status tracking (to be added later)
        # self._queue_stats: Dict[str, Any] = {}

    async def get_all_reminders(self) -> List[str]:
        """
        Get all system reminders from monitored sources.

        This is the main entry point called by context managers to collect
        all reminders that should be injected into user messages.

        Returns:
            List[str]: Combined list of reminder strings from all sources
        """
        reminders = []

        # Bash background processes
        bash_reminders = await self._get_bash_reminders()
        reminders.extend(bash_reminders)

        # TODO: Add PFC task reminders after bash testing
        # pfc_reminders = await self._get_pfc_reminders()
        # reminders.extend(pfc_reminders)

        # TODO: Add interrupt reminders
        # interrupt_reminders = self._get_interrupt_reminders()
        # reminders.extend(interrupt_reminders)

        # TODO: Add queue status reminders
        # queue_reminders = self._get_queue_reminders()
        # reminders.extend(queue_reminders)

        return reminders

    async def _get_bash_reminders(self) -> List[str]:
        """
        Get reminders for bash background processes.

        Queries the background process manager for running processes
        in the current session.

        Returns:
            List[str]: Bash process reminders
        """
        try:
            from backend.infrastructure.mcp.tools.coding.utils.background_process_manager import get_process_manager

            process_manager = get_process_manager()
            print(f"[DEBUG] StatusMonitor._get_bash_reminders: Calling get_system_reminders for session {self.session_id}")
            bash_reminders = process_manager.get_system_reminders(self.session_id)
            print(f"[DEBUG] StatusMonitor._get_bash_reminders: Got {len(bash_reminders)} bash reminders")
            if bash_reminders:
                print(f"[DEBUG] Bash reminders: {bash_reminders}")
            return bash_reminders

        except Exception as e:
            # Process manager may not be available or no processes running
            print(f"[DEBUG] StatusMonitor._get_bash_reminders: Exception: {e}")
            import traceback
            traceback.print_exc()
            return []

    # TODO: Implement PFC monitoring after bash testing
    # async def _get_pfc_reminders(self) -> List[str]:
    #     """
    #     Get reminders for PFC simulation tasks.
    #
    #     Queries the PFC WebSocket server for task status, detects
    #     status transitions, and generates completion notifications.
    #
    #     Returns:
    #         List[str]: PFC task reminders
    #     """
    #     pass

    # TODO: Implement interrupt monitoring
    # def _get_interrupt_reminders(self) -> List[str]:
    #     """
    #     Get reminder for user interrupt status.
    #
    #     Returns:
    #         List[str]: Interrupt reminder if flag is set
    #     """
    #     pass

    # TODO: Implement queue monitoring
    # def _get_queue_reminders(self) -> List[str]:
    #     """
    #     Get reminders for task queue status.
    #
    #     Returns:
    #         List[str]: Queue status reminders
    #     """
    #     pass


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
