"""PFC execution service for foreground/background task management.

Application layer service coordinating PFC task execution:
- Foreground-to-background conversion (ctrl+b)
- Task state queries
- Foreground execution lifecycle management
- Integration with pfc-server

Bridges presentation layer (WebSocket handlers, MCP tools) and infrastructure layer
(PfcForegroundTaskRegistry, PfcTaskManager, PfcTaskNotificationService).

Used by both:
- pfc_execute_task tool (agent tasks)
- UserPfcConsoleHandler (user console commands)
"""

from typing import Optional, TYPE_CHECKING

from backend.infrastructure.pfc.foreground_registry import (
    get_pfc_foreground_registry,
    PfcForegroundTaskRegistry,
)
from backend.infrastructure.pfc.foreground_handle import (
    PfcForegroundExecutionHandle,
    PfcForegroundExecutionResult,
)
from backend.infrastructure.pfc.task_manager import (
    get_pfc_task_manager,
    PfcTaskManager,
)

if TYPE_CHECKING:
    from backend.application.services.notifications.pfc_task_notification_service import (
        PfcTaskNotificationService,
    )


class PfcExecutionService:
    """Service for managing PFC task execution state.

    Provides application-layer interface for:
    - Requesting foreground-to-background conversion
    - Checking if a session has a running foreground task
    - Getting task status

    Note: PFC only supports single task concurrency. Each session
    can have at most one active task at any time.

    Example:
        service = get_pfc_execution_service()

        # Check if session has foreground task
        if service.has_foreground_task(session_id):
            # Request move to background (triggered by ctrl+b)
            success = service.request_move_to_background(session_id)
    """

    def __init__(
        self,
        registry: Optional[PfcForegroundTaskRegistry] = None,
        task_manager: Optional[PfcTaskManager] = None,
    ):
        """Initialize the service.

        Args:
            registry: Optional PfcForegroundTaskRegistry instance for testing.
                     If None, uses the global singleton.
            task_manager: Optional PfcTaskManager instance for testing.
                         If None, uses the global singleton.
        """
        self._registry = registry or get_pfc_foreground_registry()
        self._task_manager = task_manager or get_pfc_task_manager()

    def request_move_to_background(self, session_id: str) -> bool:
        """Request a foreground PFC task to move to background.

        Called when user presses ctrl+b. Signals the running foreground
        task to stop waiting and return MoveToBackgroundRequest.

        Args:
            session_id: Session ID of the task to move

        Returns:
            True if signal was sent successfully
            False if no foreground task found for this session
        """
        return self._registry.request_move_to_background(session_id)

    def has_foreground_task(self, session_id: str) -> bool:
        """Check if a session has a running foreground PFC task.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has an active foreground task
        """
        return self._registry.has_foreground_task(session_id)

    def get_foreground_task_id(self, session_id: str) -> Optional[str]:
        """Get the task ID for a session's foreground task.

        Args:
            session_id: Session ID to look up

        Returns:
            Task ID if found, None otherwise
        """
        return self._registry.get_task_id(session_id)

    def has_active_task(self, session_id: str) -> bool:
        """Check if a session has any active (non-terminal) PFC task.

        This includes both foreground and background tasks.

        Args:
            session_id: Session ID to check

        Returns:
            True if session has an active task
        """
        return self._task_manager.has_active_tasks(session_id)

    def get_active_task_ids(self, session_id: str) -> list:
        """Get list of active task IDs for a session.

        Args:
            session_id: Session ID to check

        Returns:
            List of active task IDs
        """
        return self._task_manager.get_active_task_ids(session_id)


# Singleton instance
_service: Optional[PfcExecutionService] = None


def get_pfc_execution_service() -> PfcExecutionService:
    """Get the global PFC execution service instance."""
    global _service
    if _service is None:
        _service = PfcExecutionService()
    return _service
