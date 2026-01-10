"""Bash execution service for foreground/background process management.

Application layer service coordinating bash tool execution:
- Foreground-to-background conversion (ctrl+b)
- Process state queries

Bridges presentation layer (WebSocket handlers) and infrastructure layer
(ForegroundTaskRegistry, BackgroundProcessManager).
"""

from typing import Optional

from backend.infrastructure.shell.foreground_task_registry import (
    get_foreground_task_registry,
    ForegroundTaskRegistry,
)


class BashExecutionService:
    """Service for managing bash tool execution state.

    Provides application-layer interface for:
    - Requesting foreground-to-background conversion
    - Checking if a session has a running foreground process

    Example:
        service = get_bash_execution_service()

        # Check if session has foreground process
        if service.has_foreground_process(session_id):
            # Request move to background (triggered by ctrl+b)
            success = service.request_move_to_background(session_id)
    """

    def __init__(self, registry: Optional[ForegroundTaskRegistry] = None):
        """Initialize the service.

        Args:
            registry: Optional ForegroundTaskRegistry instance for testing.
                     If None, uses the global singleton.
        """
        self._registry = registry or get_foreground_task_registry()

    def request_move_to_background(self, session_id: str) -> bool:
        """Request a foreground process to move to background.

        Called when user presses ctrl+b. Signals the running foreground
        process to stop waiting and return MoveToBackgroundRequest.

        Args:
            session_id: Session ID of the process to move

        Returns:
            True if signal was sent successfully
            False if no foreground process found for this session
        """
        return self._registry.request_move_to_background(session_id)

    def has_foreground_process(self, session_id: str) -> bool:
        """Check if a session has a running foreground bash process.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has an active foreground process
        """
        return self._registry.has_foreground_process(session_id)


# Singleton instance
_service: Optional[BashExecutionService] = None


def get_bash_execution_service() -> BashExecutionService:
    """Get the global bash execution service instance."""
    global _service
    if _service is None:
        _service = BashExecutionService()
    return _service
