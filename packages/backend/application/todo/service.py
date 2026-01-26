"""
Todo Service - Application layer service for todo management.

Provides business logic for retrieving and managing todo items across sessions.
All methods require explicit agent_profile parameter for workspace resolution.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from backend.infrastructure.storage.todo_storage import get_todo_storage
from backend.shared.utils.workspace import get_workspace_for_profile

logger = logging.getLogger(__name__)


class TodoService:
    """
    Service for managing todo items.

    Handles business logic for todo retrieval and filtering,
    coordinating between workspace resolution and todo storage.
    """

    def __init__(self):
        """Initialize todo service."""
        self.storage = get_todo_storage()
        self.logger = logger

    async def get_current_todo(
        self,
        agent_profile: str,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the currently in-progress todo for a workspace.

        Returns the first todo with status="in_progress" from the workspace.
        This is used for frontend display to show what the agent is currently working on.

        Args:
            agent_profile: Agent profile type (e.g., "pfc_expert", "disabled").
                          Determines which workspace to use.
            session_id: Optional session identifier (for PFC profile workspace sync).

        Returns:
            Dict containing todo information if found, None otherwise
            {
                "todo_id": str,
                "content": str,          # Imperative form
                "activeForm": str,       # Present continuous form (for display)
                "status": str,
                "session_id": str,
                "created_at": float,
                "updated_at": float,
                "metadata": dict
            }
        """
        try:
            workspace = await get_workspace_for_profile(agent_profile, session_id)

            # Load all todos from workspace
            todos = self.storage.load_todos(workspace)

            # Find first in_progress todo
            for todo in todos:
                if todo.get("status") == "in_progress":
                    self.logger.debug(f"Found in_progress todo: {todo.get('content')}")
                    return todo

            self.logger.debug("No in_progress todo found")
            return None

        except Exception as e:
            self.logger.error(f"Failed to get current todo: {e}")
            return None

    async def get_all_todos(
        self,
        agent_profile: str,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all todos for a workspace.

        Args:
            agent_profile: Agent profile type (e.g., "pfc_expert", "disabled").
            session_id: Optional session identifier (for PFC profile workspace sync).

        Returns:
            List of all todos (sorted by update time, most recent first)
        """
        try:
            workspace = await get_workspace_for_profile(agent_profile, session_id)
            todos = self.storage.load_all_session_todos(workspace)
            return todos
        except Exception as e:
            self.logger.error(f"Failed to get all todos: {e}")
            return []

    async def get_pending_todos(
        self,
        agent_profile: str,
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pending and in_progress todos for a workspace.

        Args:
            agent_profile: Agent profile type (e.g., "pfc_expert", "disabled").
            session_id: Optional session identifier (for PFC profile workspace sync).
            limit: Maximum number of todos to return

        Returns:
            List of pending/in_progress todos
        """
        try:
            workspace = await get_workspace_for_profile(agent_profile, session_id)
            todos = self.storage.get_pending_todos(workspace, limit)
            return todos
        except Exception as e:
            self.logger.error(f"Failed to get pending todos: {e}")
            return []


# Global singleton instance
_service_instance = None


def get_todo_service() -> TodoService:
    """
    Get the global TodoService singleton instance.

    Returns:
        TodoService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = TodoService()
    return _service_instance
