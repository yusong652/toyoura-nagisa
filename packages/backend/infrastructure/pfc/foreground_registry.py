"""PFC Foreground Task Registry for ctrl+b signal handling.

Tracks the running foreground PFC task and enables external signals
(like ctrl+b from CLI) to trigger move-to-background conversion.

Note: PFC only supports single task concurrency, so this registry
tracks at most one foreground task at a time (per session).
"""

from threading import Lock
from typing import Dict, Optional

from .foreground_handle import PfcForegroundExecutionHandle


class PfcForegroundTaskRegistry:
    """Registry for tracking foreground PFC task.

    Enables external components (WebSocket handlers) to signal
    a running foreground PFC task to move to background.

    Since PFC only supports single task concurrency, each session
    has at most one active foreground task at any time.

    Thread-safe: Uses Lock for concurrent access protection.
    """

    def __init__(self) -> None:
        self._handles: Dict[str, PfcForegroundExecutionHandle] = {}
        self._lock = Lock()

    def register(self, session_id: str, handle: PfcForegroundExecutionHandle) -> None:
        """Register a foreground PFC task handle.

        Args:
            session_id: Session ID for task isolation
            handle: PfcForegroundExecutionHandle to register
        """
        with self._lock:
            self._handles[session_id] = handle

    def unregister(self, session_id: str) -> None:
        """Unregister a foreground PFC task handle.

        Args:
            session_id: Session ID to unregister
        """
        with self._lock:
            self._handles.pop(session_id, None)

    def get(self, session_id: str) -> Optional[PfcForegroundExecutionHandle]:
        """Get a foreground PFC task handle by session ID.

        Args:
            session_id: Session ID to look up

        Returns:
            PfcForegroundExecutionHandle if found, None otherwise
        """
        with self._lock:
            return self._handles.get(session_id)

    def request_move_to_background(self, session_id: str) -> bool:
        """Signal a foreground PFC task to move to background.

        Called by WebSocket handler when user presses ctrl+b.

        Args:
            session_id: Session ID of the task to move

        Returns:
            True if signal was sent, False if no task found
        """
        with self._lock:
            handle = self._handles.get(session_id)
            if handle is not None:
                handle.request_move_to_background()
                return True
            return False

    def has_foreground_task(self, session_id: str) -> bool:
        """Check if a session has a running foreground PFC task.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has a foreground PFC task
        """
        with self._lock:
            return session_id in self._handles

    def get_task_id(self, session_id: str) -> Optional[str]:
        """Get the task ID for a session's foreground task.

        Args:
            session_id: Session ID to look up

        Returns:
            Task ID if found, None otherwise
        """
        with self._lock:
            handle = self._handles.get(session_id)
            return handle.task_id if handle else None


# Singleton instance
_registry: Optional[PfcForegroundTaskRegistry] = None


def get_pfc_foreground_registry() -> PfcForegroundTaskRegistry:
    """Get the global PFC foreground task registry instance."""
    global _registry
    if _registry is None:
        _registry = PfcForegroundTaskRegistry()
    return _registry
