"""
Todo Monitor - Full todo list reminders with periodic injection.

Every reminder contains the entire todo list shared across all sessions so the LLM
always sees the authoritative state (pending, in-progress, and completed items).
Cross-session persistence ensures todos are visible to all sessions in the workspace.

Implements Claude Code-style periodic reminders: injects todo list every N tool calls
even when todo list is empty, to prompt the LLM to consider using the TodoWrite tool.
"""

import asyncio
import logging
from typing import List

from backend.infrastructure.storage.todo_storage import get_todo_storage
from backend.shared.utils.workspace import get_workspace_for_profile

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

    Note: This monitor requires agent_profile for workspace resolution.
    """

    # Class-level storage for activity counts per session
    # Tracks both conversation turns and tool iterations
    _activity_counts = {}
    _last_reminder_counts = {}

    # Configurable reminder interval (default: every 3 activities)
    # Activities include: user messages + tool call iterations
    DEFAULT_REMINDER_INTERVAL = 3

    def _ensure_session_initialized(self) -> None:
        """Ensure session tracking is initialized."""
        if self.session_id not in self._activity_counts:
            self._activity_counts[self.session_id] = 0
            self._last_reminder_counts[self.session_id] = 0

    def track_conversation_turn(self) -> None:
        """Track a conversation turn (user message) for this session."""
        self._ensure_session_initialized()
        self._activity_counts[self.session_id] += 1
        logger.debug(f"Session {self.session_id[:8]} conversation turn, activity count: {self._activity_counts[self.session_id]}")

    def track_iteration(self) -> None:
        """Track a tool call iteration for this session."""
        self._ensure_session_initialized()
        self._activity_counts[self.session_id] += 1
        logger.debug(f"Session {self.session_id[:8]} iteration, activity count: {self._activity_counts[self.session_id]}")

    def get_reminder_interval(self) -> int:
        """Get the configured reminder interval or use default."""
        # TODO: Load from configuration when config system is ready
        # from backend.config import get_todo_reminder_interval
        # return get_todo_reminder_interval()
        return self.DEFAULT_REMINDER_INTERVAL

    def should_show_periodic_reminder(self) -> bool:
        """
        Check if we should show a periodic todo reminder.

        Returns true every N activities (conversation turns + iterations).
        """
        if self.session_id not in self._activity_counts:
            return False

        current_count = self._activity_counts[self.session_id]
        last_reminder = self._last_reminder_counts.get(self.session_id, 0)
        interval = self.get_reminder_interval()

        # Show reminder if we've had INTERVAL activities since last reminder
        if current_count - last_reminder >= interval:
            self._last_reminder_counts[self.session_id] = current_count
            return True

        return False

    async def get_reminders(self, agent_profile: str = "general") -> List[str]:
        """
        Get reminders for the full todo list.

        Claude Code-style behavior:
        - Always returns reminders every N conversation turns
        - Shows actual todos when they exist
        - Shows empty list prompt when no todos
        - Helps save context by periodic injection

        Args:
            agent_profile: Agent profile type for workspace resolution.

        Returns:
            List[str]: Todo list reminder blocks
        """
        try:
            workspace = await get_workspace_for_profile(agent_profile, self.session_id)
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
            # Format existing todos (Claude Code exact format)
            lines = ["Here are the existing contents of your todo list:", ""]

            # Build the todo list with surrounding brackets
            todo_lines = []
            for i, todo in enumerate(todos, 1):
                status = todo.get("status", "pending")
                content = todo.get("content", "Todo item")
                # Claude Code format: "N. [status] content"
                line = f"{i}. [{status}] {content}"
                todo_lines.append(line)

            # Join with newlines and wrap in brackets
            lines.append("[" + "\n".join(todo_lines) + "]")
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
