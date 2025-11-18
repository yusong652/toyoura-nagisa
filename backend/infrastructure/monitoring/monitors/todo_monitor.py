"""
Todo Monitor - Todo item completion tracking.

Implements Claude Code-compatible todo monitoring with intelligent notification:
1. Unnotified completed todos → One-time completion notification + mark as notified
2. Pending/in-progress todos → No reminders (use TodoWrite tool to check)
3. Already notified completed todos → Excluded (no reminder)
"""

import logging
from typing import List
from .base_monitor import BaseMonitor

logger = logging.getLogger(__name__)


class TodoMonitor(BaseMonitor):
    """
    Monitor for todo item completion tracking.

    Follows Claude Code pattern:
    - Persistent notification tracking (notified flag in storage)
    - One-time completion notifications
    - Cross-session awareness
    """

    async def get_reminders(self) -> List[str]:
        """
        Get reminders for todo items with intelligent notification tracking.

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
                created_at = todo.get("created_at")
                updated_at = todo.get("updated_at")

                # Format time info
                if created_at and updated_at:
                    from backend.infrastructure.mcp.utils.time_utils import format_time_range
                    time_info = format_time_range(created_at, updated_at)
                else:
                    time_info = "time unknown"

                # Generate notification (no session marker for cross-session awareness)
                notification = (
                    f"Todo completed: {content}, {time_info}."
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
