"""
Todo Monitor - Full todo list reminders.

Every reminder contains the entire todo list shared across all sessions so the LLM
always sees the authoritative state (pending, in-progress, and completed items).
Cross-session persistence ensures todos are visible to all sessions in the workspace.
"""

import logging
from typing import List

from backend.infrastructure.storage.todo_storage import get_todo_storage
from backend.shared.utils.workspace import get_workspace_for_session_sync

from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class TodoMonitor(BaseMonitor):
    """
    Monitor for todo items.

    Emits the entire todo list as a reminder whenever todos exist in the workspace.
    All sessions share the same todo list for cross-session continuity.
    """

    async def get_reminders(self) -> List[str]:
        """
        Get reminders for the full todo list.

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
            # session_id is now optional and not used for isolation
            todos = storage.load_todos(workspace)
        except Exception as e:
            logger.debug(f"Failed to load todos for reminders: {e}")
            return []

        if not todos:
            return []

        lines = ["Here are the existing contents of your todo list:", ""]
        for i, todo in enumerate(todos, 1):
            status = todo.get("status", "pending")
            content = todo.get("content", "Todo item")

            # Claude Code format: "1. [status] content"
            line = f"{i}. [{status}] {content}"
            lines.append(line)

        reminder_text = "\n".join(lines)
        reminder_block = f"<system-reminder>\n{reminder_text}\n</system-reminder>"

        return [reminder_block]
