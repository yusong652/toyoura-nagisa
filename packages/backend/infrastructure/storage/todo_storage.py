"""
Todo Storage - Persistent and in-memory storage for todo items.

Implements two storage modes:
    - Persistent mode (MainAgent): workspace/todos.json (shared across all sessions)
    - Memory mode (SubAgent): in-memory storage isolated per session

Storage Strategy:
    - Workspace-level storage: workspace/todos.json (shared across all sessions)
    - Cross-session persistence: All sessions share the same todo list
    - Workspace resolution: Uses workspace.py for profile-aware paths
    - Auto-clear on completion: Delete file when saving empty list
    - Memory mode: Session-scoped in-memory storage for SubAgents

Data Schema:
    {
        "todos": [
            {
                "todo_id": "a1b2c3d4",
                "session_id": "full-uuid-here",
                "created_at": 1700000000.0,
                "updated_at": 1700000000.0,
                "content": "Todo description (imperative form)",
                "activeForm": "Active description (present continuous)",
                "status": "pending" | "in_progress" | "completed",
                "metadata": {}
            }
        ]
    }
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# In-memory storage for non-persistent mode (SubAgents)
# Key: session_id, Value: list of todo items
_memory_todos: Dict[str, List[Dict[str, Any]]] = {}


class TodoStorage:
    """
    Persistent storage manager for todo items.

    Stores todos in workspace directories for project-level persistence,
    enabling cross-session tracking similar to PFC task management.
    """

    def __init__(self):
        """Initialize todo storage manager."""
        self.logger = logger

    def _get_todos_path(self, workspace: Path) -> Path:
        """
        Get path to workspace's shared todos.json file.

        Args:
            workspace: Workspace directory (from workspace.py)

        Returns:
            Path to todos.json file
        """
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace / "todos.json"

    def _load_todos_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Load todos from JSON file.

        Args:
            file_path: Path to todos.json

        Returns:
            List of todo dictionaries (empty if file doesn't exist)
        """
        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("todos", [])
        except Exception as e:
            self.logger.error(f"Failed to load todos from {file_path}: {e}")
            return []

    def _save_todos_to_file(self, file_path: Path, todos: List[Dict[str, Any]]) -> None:
        """
        Save todos to JSON file with atomic write.

        Args:
            file_path: Path to todos.json
            todos: List of todo dictionaries
        """
        try:
            # Atomic write pattern (from PFC persistence)
            temp_file = file_path.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump({"todos": todos}, f, indent=2, ensure_ascii=False)

            # Atomic replace
            temp_file.replace(file_path)

        except Exception as e:
            self.logger.error(f"Failed to save todos to {file_path}: {e}")
            raise

    def save_todos(
        self,
        workspace: Path,
        session_id: str,
        todos: List[Dict[str, Any]],
        persistent: bool = True
    ) -> None:
        """
        Save todos for workspace or in-memory (session-scoped).

        This implements the "full update" pattern similar to Claude Code's TodoWrite,
        where the entire todo list is replaced on each update.

        Special behavior (Claude Code compatible):
        - If todos list is empty, delete the todos.json file instead of saving empty file
        - This ensures clean workspace without stale empty todo files

        Args:
            workspace: Workspace directory path
            session_id: Session identifier (for tracking which session created/updated the todo)
            todos: Complete list of todos (replaces existing)
            persistent: If True, save to local file (MainAgent).
                       If False, save to in-memory storage (SubAgent).
        """
        # Ensure all todos have required fields
        current_time = time.time()
        for todo in todos:
            if "todo_id" not in todo:
                todo["todo_id"] = uuid.uuid4().hex[:8]
            if "session_id" not in todo:
                todo["session_id"] = session_id
            if "created_at" not in todo:
                todo["created_at"] = current_time
            todo["updated_at"] = current_time
            if "metadata" not in todo:
                todo["metadata"] = {}

        # Non-persistent mode: save to memory
        if not persistent:
            _memory_todos[session_id] = todos
            self.logger.debug(f"Saved {len(todos)} todo(s) to memory (session {session_id[:8]})")
            return

        # Persistent mode: save to file
        file_path = self._get_todos_path(workspace)

        # Handle empty list: delete the file instead of saving empty JSON
        if not todos:
            if file_path.exists():
                file_path.unlink()
                self.logger.info(f"Deleted todos file for workspace (empty list)")
            else:
                self.logger.debug(f"No todos file to delete for workspace")
            return

        self._save_todos_to_file(file_path, todos)
        self.logger.info(f"Saved {len(todos)} todo(s) to workspace (from session {session_id[:8]})")

    def load_todos(
        self,
        workspace: Path,
        session_id: Optional[str] = None,
        persistent: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Load todos from workspace or in-memory storage.

        Args:
            workspace: Workspace directory path
            session_id: Session identifier (required for non-persistent mode)
            persistent: If True, load from local file (MainAgent).
                       If False, load from in-memory storage (SubAgent).

        Returns:
            List of todo dictionaries
        """
        # Non-persistent mode: load from memory
        if not persistent:
            todos = _memory_todos.get(session_id, []) if session_id else []
            self.logger.debug(f"Loaded {len(todos)} todo(s) from memory (session {session_id[:8] if session_id else 'unknown'})")
            return todos

        # Persistent mode: load from file
        file_path = self._get_todos_path(workspace)
        todos = self._load_todos_from_file(file_path)
        self.logger.debug(f"Loaded {len(todos)} todo(s) from workspace")
        return todos

    def load_all_session_todos(self, workspace: Path) -> List[Dict[str, Any]]:
        """
        Load todos from the workspace (now shared across all sessions).

        This method now simply returns the shared workspace todos,
        as all sessions share the same todo list.

        Args:
            workspace: Workspace directory path

        Returns:
            List of all todos, sorted by update time (desc)
        """
        # Since we now use a single shared file, just load it
        todos = self.load_todos(workspace)

        # Sort by updated_at descending (most recent first)
        todos.sort(key=lambda t: t.get("updated_at", 0), reverse=True)

        self.logger.debug(f"Loaded {len(todos)} todo(s) from workspace")
        return todos

    def get_pending_todos(
        self,
        workspace: Path,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pending todos for status reminders.

        Args:
            workspace: Workspace directory path
            limit: Maximum number of todos to return (None = all)

        Returns:
            List of pending todos (most recent first)
        """
        all_todos = self.load_all_session_todos(workspace)

        pending = [
            todo for todo in all_todos
            if todo.get("status") in ["pending", "in_progress"]
        ]

        return pending[:limit] if limit else pending


    def clear_memory_todos(self, session_id: str) -> None:
        """
        Clear in-memory todos for a session.

        Should be called when a SubAgent completes to free memory.

        Args:
            session_id: Session identifier to clear
        """
        if session_id in _memory_todos:
            del _memory_todos[session_id]
            self.logger.debug(f"Cleared memory todos for session {session_id[:8]}")


# Global singleton instance
_storage_instance = None


def get_todo_storage() -> TodoStorage:
    """
    Get the global TodoStorage singleton instance.

    Returns:
        TodoStorage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = TodoStorage()
    return _storage_instance
