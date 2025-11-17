"""
Status Monitor - Unified system status tracking for reminders

This module provides centralized monitoring for all background tasks and system states
that need to be communicated to the LLM via system-reminders:

1. Bash background processes - Local background shell tasks
2. PFC simulation tasks - Remote PFC server tasks
3. User queue messages - Messages sent during tool execution
4. User interrupt status - Response interruption notifications

The monitor is session-scoped and provides unified reminder API.
"""

import asyncio
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

        Loads interrupt state from runtime_state storage on initialization.

        Args:
            session_id: Session ID for scoped monitoring
        """
        self.session_id = session_id

        # Agent profile (set dynamically before querying reminders)
        # Used to optimize queries (e.g., skip PFC if not in PFC/general profile)
        self.agent_profile: str = "general"

        # User interrupt state management
        # - user_interrupted: Immediate flag for stopping current streaming (in-memory only)
        # - _last_response_interrupted: Persistent flag for message merging (loaded from runtime_state)
        self.user_interrupted: bool = False  # Reset each conversation turn
        self._last_response_interrupted: bool = False
        self._load_interrupt_state()

    def _load_interrupt_state(self) -> None:
        """
        Load interrupt state from runtime_state storage.

        Called during initialization to restore interrupt flag from persistent storage.
        """
        try:
            from backend.infrastructure.storage.session_manager import load_runtime_state

            runtime_state = load_runtime_state(self.session_id)
            self._last_response_interrupted = runtime_state.get("last_response_interrupted", False)

            if self._last_response_interrupted:
                logger.info(f"Loaded interrupt state for session {self.session_id[:8]}: interrupted=True")

        except Exception as e:
            logger.warning(f"Failed to load interrupt state: {e}")
            self._last_response_interrupted = False

    def was_last_response_interrupted(self) -> bool:
        """
        Check if the last response was interrupted by the user.

        This method is used by ContextManager to determine if consecutive
        user messages should be merged.

        Returns:
            bool: True if last response was interrupted
        """
        return self._last_response_interrupted

    def set_user_interrupted(self) -> None:
        """
        Set the immediate user interrupt flag.

        Called by UserInterruptHandler when user presses ESC.
        This flag is checked in real-time by ChatOrchestrator to stop streaming.

        Note: This only sets the in-memory flag. The persistent flag is set
        by set_interrupt_flag() after the interrupted response is handled.
        """
        self.user_interrupted = True
        logger.info(f"Set user_interrupted flag for session {self.session_id[:8]}")

    def reset_user_interrupted(self) -> None:
        """
        Reset the immediate user interrupt flag.

        Called at the start of each new conversation turn to prepare
        for potential interruptions.
        """
        self.user_interrupted = False

    def is_user_interrupted(self) -> bool:
        """
        Check if user has interrupted the current streaming response.

        Used by ChatOrchestrator to detect interruptions in real-time.

        Returns:
            bool: True if user pressed ESC to interrupt current response
        """
        return self.user_interrupted

    def set_interrupt_flag(self) -> None:
        """
        Set the persistent interrupt flag in both memory and storage.

        Called by ChatOrchestrator after handling an interrupted response.
        This flag will trigger message merging on the next user message.
        """
        try:
            self._last_response_interrupted = True

            from backend.infrastructure.storage.session_manager import update_runtime_state
            update_runtime_state(self.session_id, "last_response_interrupted", True)

            logger.info(f"Set last_response_interrupted flag for session {self.session_id[:8]}")

        except Exception as e:
            logger.warning(f"Failed to set interrupt flag: {e}")
            # Still set memory flag
            self._last_response_interrupted = True

    def clear_interrupt_flag(self) -> None:
        """
        Clear the interrupt flag in both memory and persistent storage.

        Called by ContextManager after handling interrupted response merge
        during initialization (_handle_interrupted_response_on_init).

        This prevents duplicate interrupt reminders when the interruption
        has already been handled by merging messages in history.
        """
        try:
            self._last_response_interrupted = False

            from backend.infrastructure.storage.session_manager import update_runtime_state
            update_runtime_state(self.session_id, "last_response_interrupted", False)

            logger.debug(f"Cleared interrupt flag for session {self.session_id[:8]}")

        except Exception as e:
            logger.warning(f"Failed to clear interrupt flag: {e}")
            # Still clear memory flag
            self._last_response_interrupted = False

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

        # Interrupt status (should be first for visibility)
        interrupt_reminders = self._get_interrupt_reminders()
        reminders.extend(interrupt_reminders)

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

        # Todo completion notifications
        todo_reminders = await self._get_todo_reminders()
        reminders.extend(todo_reminders)

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
        Get reminders for PFC simulation tasks with intelligent notification tracking.

        Implements persistent notification tracking stored in PFC server:
        1. Unnotified completed/failed tasks → One-time completion notification + mark as notified
        2. Running tasks → Continuous status reminders
        3. Already notified completed/failed tasks → Excluded (no reminder)

        The notified flag is persisted in PFC server's task storage, ensuring
        consistent behavior across sessions and server restarts.

        Only queries PFC if agent_profile is 'pfc', to avoid unnecessary
        connection attempts for other profiles.

        Returns:
            List[str]: PFC task reminders (completion alerts + running task status)
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

            wrapped_reminders = []
            completion_notifications = []
            tasks_to_mark = []  # Track tasks that need to be marked as notified

            # Step 1: Separate tasks by status and notification state
            for task in tasks:
                task_id = task.get("task_id", "unknown")
                status = task.get("status", "unknown")
                notified = task.get("notified", False)
                description = task.get("description", "No description")
                script_path = task.get("script_path", task.get("name", "unknown"))
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

                # Handle completed/failed tasks
                if status in ["completed", "failed"]:
                    if not notified:
                        # Generate one-time completion notification
                        notification = (
                            f"PFC Task {task_id}{session_marker} {status}: "
                            f"{script_path}, {time_info} - {description}. "
                            f"Use pfc_check_task_status('{task_id}') to see results."
                        )
                        completion_notifications.append(notification)
                        tasks_to_mark.append(task_id)
                    # else: already notified, skip (no reminder)

                # Handle running tasks
                elif status == "running":
                    reminder = (
                        f"PFC Task {task_id}{session_marker}: "
                        f"status=running, script={script_path}, {time_info}. "
                        f"Description: {description}"
                    )
                    wrapped_reminders.append(f"<system-reminder>\n{reminder}\n</system-reminder>")

            # Step 2: Wrap completion notifications and add them first (higher priority)
            if completion_notifications:
                wrapped_reminders = [
                    f"<system-reminder>\n{notification}\n</system-reminder>"
                    for notification in completion_notifications
                ] + wrapped_reminders

            # Step 3: Mark tasks as notified in PFC server (async, fire-and-forget)
            for task_id in tasks_to_mark:
                try:
                    asyncio.create_task(client.mark_task_notified(task_id))
                except Exception as e:
                    logger.warning(f"Failed to mark task {task_id} as notified: {e}")

            # Add tool usage hint once at the end (not repeated for each task)
            if wrapped_reminders:
                tool_hint = "<system-reminder>\nYou can check detailed output using pfc_check_task_status tool.\n</system-reminder>"
                wrapped_reminders.append(tool_hint)

            return wrapped_reminders

        except Exception as e:
            # PFC server may not be available or not running
            logger.debug(f"Failed to get PFC reminders: {e}")
            return []

    async def _get_todo_reminders(self) -> List[str]:
        """
        Get reminders for todo items with intelligent notification tracking.

        Implements persistent notification tracking stored in workspace:
        1. Unnotified completed todos → One-time completion notification + mark as notified
        2. Pending/in-progress todos → No reminders (user uses todo_list to check)
        3. Already notified completed todos → Excluded (no reminder)

        The notified flag is persisted in workspace storage (similar to PFC pattern),
        ensuring consistent behavior across sessions.

        Returns:
            List[str]: Todo completion reminders (one-time notifications only)
        """
        try:
            from backend.infrastructure.storage.todo_storage import get_todo_storage
            from backend.shared.utils.workspace import get_workspace_for_session_sync

            # Get workspace directory for this session
            workspace = get_workspace_for_session_sync(self.session_id)

            # Get unnotified completed todos (limit=3, like PFC tasks)
            storage = get_todo_storage()
            unnotified_todos = storage.get_unnotified_completed_todos(workspace, limit=3)

            if not unnotified_todos:
                return []

            wrapped_reminders = []
            todos_to_mark = []

            # Generate completion notifications
            for todo in unnotified_todos:
                todo_id = todo.get("todo_id", "unknown")
                content = todo.get("content", "No description")
                todo_session_id = todo.get("session_id", "unknown")
                created_at = todo.get("created_at")
                updated_at = todo.get("updated_at")

                # Build session marker
                todo_session_display = todo_session_id[:8] if todo_session_id != "unknown" else "unknown"
                if todo_session_id == self.session_id:
                    session_marker = " (your todo)"
                else:
                    session_marker = f" (session: {todo_session_display})"

                # Format time info
                if created_at and updated_at:
                    from backend.infrastructure.mcp.utils.time_utils import format_time_range
                    time_info = format_time_range(created_at, updated_at)
                else:
                    time_info = "time unknown"

                # Generate notification
                notification = (
                    f"Todo {todo_id}{session_marker} completed: "
                    f"{content}, {time_info}. "
                    f"Use todo_list() to see all todos."
                )

                wrapped_reminders.append(f"<system-reminder>\n{notification}\n</system-reminder>")
                todos_to_mark.append(todo_id)

            # Mark todos as notified (synchronous for simplicity)
            for todo_id in todos_to_mark:
                try:
                    storage.mark_todo_notified(workspace, todo_id)
                except Exception as e:
                    logger.warning(f"Failed to mark todo {todo_id} as notified: {e}")

            return wrapped_reminders

        except Exception as e:
            # Todo storage may not be available
            logger.debug(f"Failed to get todo reminders: {e}")
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

    def _get_interrupt_reminders(self) -> List[str]:
        """
        Get reminder for user interrupt status.

        Checks if the last response was interrupted by the user (ESC key).
        If so, generates a reminder and clears the interrupt flag in both
        memory and persistent storage.

        This reminder is typically shown when the user sends a new message
        after interrupting the previous response.

        Returns:
            List[str]: Interrupt reminder block if flag is set, empty list otherwise
        """
        if not self._last_response_interrupted:
            return []

        try:
            # Clear interrupt flag in memory
            self._last_response_interrupted = False

            # Clear interrupt flag in persistent storage
            from backend.infrastructure.storage.session_manager import update_runtime_state
            update_runtime_state(self.session_id, "last_response_interrupted", False)

            # Generate reminder
            reminder_text = "Previous response interrupted by user."
            reminder_block = f"<system-reminder>\n{reminder_text}\n</system-reminder>"

            logger.info(f"Generated interrupt reminder for session {self.session_id[:8]}")

            return [reminder_block]

        except Exception as e:
            logger.error(f"Failed to generate interrupt reminder: {e}")
            # Still clear memory flag to avoid infinite loop
            self._last_response_interrupted = False
            return []


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
