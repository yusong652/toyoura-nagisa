"""
Status Monitor - Unified system status tracking for reminders

This module provides centralized monitoring for all background tasks and system states
that need to be communicated to the LLM via system-reminders:

1. Bash background processes - Local background shell tasks
2. PFC simulation tasks - Remote PFC server tasks
3. User queue messages - Messages sent during tool execution
4. User interrupt status (TODO)

The monitor is session-scoped and provides unified reminder API.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


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

        # Agent profile (set dynamically before querying reminders)
        # Used to optimize queries (e.g., skip PFC if not in PFC/general profile)
        self.agent_profile: str = "general"

        # TODO: User interrupt state (to be added later)
        # self._last_response_interrupted: bool = False

    async def get_all_reminders(self, check_queue: bool = False) -> List[str]:
        """
        Get all system reminders from monitored sources.

        This is the main entry point called by context managers to collect
        all reminders that should be injected into user messages.

        Args:
            check_queue: Whether to check and drain queue messages (during tool recursion)

        Returns:
            List[str]: Combined list of reminder strings from all sources
        """
        reminders = []

        # Queue messages (user messages during tool recursion)
        if check_queue:
            queue_reminders = await self._get_queue_message_blocks()
            reminders.extend(queue_reminders)

        # Bash background processes
        bash_reminders = await self._get_bash_reminders()
        reminders.extend(bash_reminders)

        # PFC simulation tasks
        pfc_reminders = await self._get_pfc_reminders()
        reminders.extend(pfc_reminders)

        # TODO: Add interrupt reminders
        # interrupt_reminders = self._get_interrupt_reminders()
        # reminders.extend(interrupt_reminders)

        return reminders

    async def _get_bash_reminders(self) -> List[str]:
        """
        Get reminders for bash background processes.

        Queries the background process manager for running processes
        in the current session and wraps them in system-reminder tags.

        Returns:
            List[str]: Bash process reminder blocks (with system-reminder tags)
        """
        try:
            from backend.infrastructure.mcp.tools.coding.utils.background_process_manager import get_process_manager

            process_manager = get_process_manager()
            bash_reminders = process_manager.get_system_reminders(self.session_id)

            # Wrap each reminder in system-reminder tags
            return [
                f"<system-reminder>\n{reminder}\n</system-reminder>"
                for reminder in bash_reminders
            ]

        except Exception:
            # Process manager may not be available or no processes running
            return []

    async def _get_pfc_reminders(self) -> List[str]:
        """
        Get reminders for PFC simulation tasks.

        Queries the PFC WebSocket server for recent tasks and generates
        status reminders showing task ID, description, status, and time range.

        Shows up to 3 most recent tasks regardless of session ownership,
        since PFC can only run one task at a time (useful to see if others
        are using the server).

        Only queries PFC if agent_profile is 'pfc', to avoid unnecessary
        connection attempts for other profiles.

        Returns:
            List[str]: PFC task reminders
        """
        # Skip PFC query if not in PFC profile
        if self.agent_profile != 'pfc':
            return []

        try:
            from backend.infrastructure.pfc import get_client
            from backend.infrastructure.mcp.utils.time_utils import format_time_range

            # Get WebSocket client (auto-connects if needed)
            client = await get_client()

            # Query recent tasks (all sessions, limit=3)
            result = await client.list_tasks(
                session_id=None,  # No filter - see all tasks
                offset=0,
                limit=3
            )

            if result.get("status") != "success":
                return []

            tasks = result.get("data", [])
            if not tasks:
                return []

            reminders = []
            for task in tasks:
                task_id = task.get("task_id", "unknown")
                description = task.get("description", "No description")
                script_path = task.get("script_path", task.get("name", "unknown"))
                status = task.get("status", "unknown")
                start_time = task.get("start_time")
                end_time = task.get("end_time")
                task_session_id = task.get("session_id", "unknown")

                # Format time range
                time_info = format_time_range(start_time, end_time)

                # Build session marker
                task_session_display = task_session_id[:8] if task_session_id != "unknown" else "unknown"
                if task_session_id == self.session_id:
                    session_marker = " (your task)"
                else:
                    session_marker = f" (session: {task_session_display})"

                # Format reminder (without repeated tool hint)
                reminder = (
                    f"PFC Task {task_id}{session_marker}: "
                    f"status={status}, script={script_path}, {time_info}. "
                    f"Description: {description}"
                )
                reminders.append(reminder)

            # Wrap all task reminders in system-reminder tags
            wrapped_reminders = [
                f"<system-reminder>\n{reminder}\n</system-reminder>"
                for reminder in reminders
            ]

            # Add tool usage hint once at the end (not repeated for each task)
            if wrapped_reminders:
                tool_hint = "<system-reminder>\nYou can check detailed output using pfc_check_task_status tool.\n</system-reminder>"
                wrapped_reminders.append(tool_hint)

            return wrapped_reminders

        except Exception:
            # PFC server may not be available or not running
            return []

    async def _get_queue_message_blocks(self) -> List[str]:
        """
        Get queue messages as reminder blocks.

        This method is called when generating tool results (inject_reminders=True).
        It extracts all waiting messages from the queue, merges them using the
        same strategy as external scenarios, and formats them as system-reminder blocks.

        Extracted messages are removed from the queue, as they've been delivered
        to the LLM via reminders and don't need to be processed as separate messages.

        Returns:
            List[str]: Formatted system-reminder blocks
        """
        try:
            from backend.infrastructure.messaging.session_queue_manager import get_queue_manager

            queue_manager = get_queue_manager()

            # Drain queue and get all messages
            messages = await queue_manager.drain_queue_for_reminders(self.session_id)

            if not messages:
                return []

            # Use the same merge strategy as external scenarios
            # _merge_messages() handles both single and multiple messages
            merged_message = queue_manager._merge_messages(messages)
            merged_text = merged_message.get('message', '')

            # Format as reminder text
            reminder_text = (
                f"The user sent the following message:\n{merged_text}\n\n"
                "Please address this message and continue with your tasks."
            )

            # Wrap in system-reminder block
            reminder_block = f"<system-reminder>\n{reminder_text}\n</system-reminder>"

            logger.info(
                f"Converted {len(messages)} queue message(s) to 1 reminder block"
            )

            return [reminder_block]

        except Exception as e:
            logger.error(f"Failed to get queue message blocks: {e}")
            return []

    # TODO: Implement interrupt monitoring
    # def _get_interrupt_reminders(self) -> List[str]:
    #     """
    #     Get reminder for user interrupt status.
    #
    #     Returns:
    #         List[str]: Interrupt reminder if flag is set
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
