"""
Todo Storage - Persistent storage for todo items.

Implements persistent todo storage in workspace directories for project-level tracking.

Storage Strategy:
    - Session-isolated storage: workspace/sessions/{session_id}/todos.json
    - Cross-session querying: Load all session todos for global awareness
    - Workspace resolution: Uses workspace.py for profile-aware paths
    - Auto-clear on completion: Delete file when saving empty list

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


class TodoStorage:
    """
    Persistent storage manager for todo items.

    Stores todos in workspace directories for project-level persistence,
    enabling cross-session tracking similar to PFC task management.
    """

    def __init__(self):
        """Initialize todo storage manager."""
        self.logger = logger

    def _get_session_todos_path(self, workspace: Path, session_id: str) -> Path:
        """
        Get path to session's todos.json file.

        Args:
            workspace: Workspace directory (from workspace.py)
            session_id: Session identifier

        Returns:
            Path to todos.json file
        """
        session_dir = workspace / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir / "todos.json"

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
        todos: List[Dict[str, Any]]
    ) -> None:
        """
        Save todos for a session (full replacement).

        This implements the "full update" pattern similar to Claude Code's TodoWrite,
        where the entire todo list is replaced on each update.

        Special behavior (Claude Code compatible):
        - If todos list is empty, delete the todos.json file instead of saving empty file
        - This ensures clean workspace without stale empty todo files

        Args:
            workspace: Workspace directory path
            session_id: Session identifier
            todos: Complete list of todos (replaces existing)
        """
        file_path = self._get_session_todos_path(workspace, session_id)

        # Handle empty list: delete the file instead of saving empty JSON
        if not todos:
            if file_path.exists():
                file_path.unlink()
                self.logger.info(f"✓ Deleted todos file for session {session_id[:8]} (empty list)")
            else:
                self.logger.debug(f"No todos file to delete for session {session_id[:8]}")
            return

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

        self._save_todos_to_file(file_path, todos)
        self.logger.info(f"✓ Saved {len(todos)} todo(s) for session {session_id[:8]}")

    def load_todos(self, workspace: Path, session_id: str) -> List[Dict[str, Any]]:
        """
        Load todos for a specific session.

        Args:
            workspace: Workspace directory path
            session_id: Session identifier

        Returns:
            List of todo dictionaries for the session
        """
        file_path = self._get_session_todos_path(workspace, session_id)
        todos = self._load_todos_from_file(file_path)
        self.logger.debug(f"Loaded {len(todos)} todo(s) for session {session_id[:8]}")
        return todos

    def load_all_session_todos(self, workspace: Path) -> List[Dict[str, Any]]:
        """
        Load todos from all sessions in the workspace (cross-session querying).

        This enables cross-session awareness similar to PFC task tracking,
        where new sessions can see todos from previous sessions.

        Args:
            workspace: Workspace directory path

        Returns:
            List of all todos across all sessions, sorted by update time (desc)
        """
        sessions_dir = workspace / "sessions"
        if not sessions_dir.exists():
            return []

        all_todos = []

        # Iterate through all session directories
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            todos_file = session_dir / "todos.json"
            if todos_file.exists():
                session_todos = self._load_todos_from_file(todos_file)
                all_todos.extend(session_todos)

        # Sort by updated_at descending (most recent first)
        all_todos.sort(key=lambda t: t.get("updated_at", 0), reverse=True)

        self.logger.debug(f"Loaded {len(all_todos)} todo(s) across all sessions")
        return all_todos

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
