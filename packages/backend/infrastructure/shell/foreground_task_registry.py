"""Foreground Task Registry for ctrl+b signal handling.

Tracks running foreground bash processes and enables external signals
(like ctrl+b from CLI) to trigger move-to-background conversion.
"""

from threading import Lock
from typing import Dict, Optional

from .executor import ForegroundExecutionHandle


class ForegroundTaskRegistry:
    """Registry for tracking foreground bash processes.

    Enables external components (WebSocket handlers) to signal
    a running foreground process to move to background.

    Thread-safe: Uses Lock for concurrent access protection.
    """

    def __init__(self) -> None:
        self._handles: Dict[str, ForegroundExecutionHandle] = {}
        self._lock = Lock()

    def register(self, session_id: str, handle: ForegroundExecutionHandle) -> None:
        """Register a foreground process handle.

        Args:
            session_id: Session ID for process isolation
            handle: ForegroundExecutionHandle to register
        """
        with self._lock:
            self._handles[session_id] = handle

    def unregister(self, session_id: str) -> None:
        """Unregister a foreground process handle.

        Args:
            session_id: Session ID to unregister
        """
        with self._lock:
            self._handles.pop(session_id, None)

    def get(self, session_id: str) -> Optional[ForegroundExecutionHandle]:
        """Get a foreground process handle by session ID.

        Args:
            session_id: Session ID to look up

        Returns:
            ForegroundExecutionHandle if found, None otherwise
        """
        with self._lock:
            return self._handles.get(session_id)

    def request_move_to_background(self, session_id: str) -> bool:
        """Signal a foreground process to move to background.

        Called by WebSocket handler when user presses ctrl+b.

        Args:
            session_id: Session ID of the process to move

        Returns:
            True if signal was sent, False if no process found
        """
        with self._lock:
            handle = self._handles.get(session_id)
            if handle is not None:
                handle.request_move_to_background()
                return True
            return False

    def has_foreground_process(self, session_id: str) -> bool:
        """Check if a session has a running foreground process.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has a foreground process
        """
        with self._lock:
            return session_id in self._handles


# Singleton instance
_registry: Optional[ForegroundTaskRegistry] = None


def get_foreground_task_registry() -> ForegroundTaskRegistry:
    """Get the global foreground task registry instance."""
    global _registry
    if _registry is None:
        _registry = ForegroundTaskRegistry()
    return _registry
