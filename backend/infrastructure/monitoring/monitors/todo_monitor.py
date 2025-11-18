"""
Todo Monitor - Full todo list reminders with periodic injection.

Every reminder contains the entire todo list shared across all sessions so the LLM
always sees the authoritative state (pending, in-progress, and completed items).
Cross-session persistence ensures todos are visible to all sessions in the workspace.

Implements Claude Code-style periodic reminders: injects todo list every N tool calls
even when todo list is empty, to prompt the LLM to consider using the TodoWrite tool.
"""

import logging
from typing import List

from backend.infrastructure.storage.todo_storage import get_todo_storage
from backend.shared.utils.workspace import get_workspace_for_session_sync

from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class TodoMonitor(BaseMonitor):
    """
    Monitor for todo items with periodic reminders.

    Emits the entire todo list as a reminder whenever todos exist in the workspace.
    All sessions share the same todo list for cross-session continuity.

    Additionally implements Claude Code-style periodic injection:
    - Tracks conversation turns across the session
    - Injects reminder every N conversation turns
    - Shows actual todos when present, empty reminder otherwise
    - Helps save context by not injecting todos on every turn
    """

    # Class-level storage for conversation turn counts per session
    _conversation_counts = {}
    _last_reminder_counts = {}

    # Configurable reminder interval (default: every 3 turns like Claude Code)
    # Can be overridden via configuration
    DEFAULT_REMINDER_INTERVAL = 3

    def track_conversation_turn(self) -> None:
        """Track a conversation turn (user message) for this session."""
        if self.session_id not in self._conversation_counts:
            self._conversation_counts[self.session_id] = 0
            self._last_reminder_counts[self.session_id] = 0

        self._conversation_counts[self.session_id] += 1
        logger.debug(f"Session {self.session_id[:8]} conversation turn: {self._conversation_counts[self.session_id]}")

    def get_reminder_interval(self) -> int:
        """Get the configured reminder interval or use default."""
        # TODO: Load from configuration when config system is ready
        # from backend.config import get_todo_reminder_interval
        # return get_todo_reminder_interval()
        return self.DEFAULT_REMINDER_INTERVAL

    def should_show_periodic_reminder(self) -> bool:
        """
        Check if we should show a periodic todo reminder.

        Returns true every N conversation turns to inject todo state.
        """
        if self.session_id not in self._conversation_counts:
            return False

        current_count = self._conversation_counts[self.session_id]
        last_reminder = self._last_reminder_counts.get(self.session_id, 0)
        interval = self.get_reminder_interval()

        # Show reminder if we've had INTERVAL turns since last reminder
        if current_count - last_reminder >= interval:
            self._last_reminder_counts[self.session_id] = current_count
            return True

        return False

    async def get_reminders(self) -> List[str]:
        """
        Get reminders for the full todo list.

        Claude Code-style behavior:
        - Always returns reminders every N conversation turns
        - Shows actual todos when they exist
        - Shows empty list prompt when no todos
        - Helps save context by periodic injection

        Returns:
            List[str]: Todo list reminder blocks
        """
        try:
            workspace = get_workspace_for_session_sync(self.session_id)
        except Exception as e:
            logger.debug(f"Unable to resolve workspace for todo reminders: {e}")
            return []

        try:
            storage = get_todo_storage()
            # Load workspace-level todos (shared across all sessions)
            todos = storage.load_todos(workspace)
        except Exception as e:
            logger.debug(f"Failed to load todos for reminders: {e}")
            return []

        # Check if we should show periodic reminder
        should_remind = self.should_show_periodic_reminder()

        # Only show reminders at the configured interval (Claude Code style)
        if not should_remind:
            return []

        # Show appropriate reminder based on todo state
        if todos:
            # Format existing todos
            lines = ["Here are the existing contents of your todo list:", ""]
            for i, todo in enumerate(todos, 1):
                status = todo.get("status", "pending")
                content = todo.get("content", "Todo item")

                # Claude Code format: "1. [status] content"
                line = f"{i}. [{status}] {content}"
                lines.append(line)

            reminder_text = "\n".join(lines)
        else:
            # Empty list reminder (Claude Code style)
            reminder_text = (
                "This is a reminder that your todo list is currently empty. "
                "DO NOT mention this to the user explicitly because they are already aware. "
                "If you are working on tasks that would benefit from a todo list please use the TodoWrite tool to create one. "
                "If not, please feel free to ignore. Again do not mention this message to the user."
            )

        reminder_block = f"<system-reminder>\n{reminder_text}\n</system-reminder>"
        return [reminder_block]
