"""
Background Process Notification Service - DDD Application Layer

This service manages real-time notifications for background bash processes,
coordinating between the BackgroundProcessManager and WebSocket frontend.

DDD Role: Application Service
- Monitors background processes and pushes status updates to frontend
- Provides recent output (last 5 lines) for compact UI display
- Handles process lifecycle notifications (started/output_update/completed/killed)
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


class BackgroundProcessNotificationService:
    """
    Application Service for Background Process Notifications.

    Monitors background bash processes and sends real-time updates to frontend
    via WebSocket. Provides recent output (last 5 lines) for compact display.

    Architecture:
    - Async monitoring loop per process
    - Push notifications when new output arrives
    - Automatic cleanup on process completion
    """

    # Configuration
    NOTIFICATION_INTERVAL_SECONDS = 1  # Check and push interval (seconds)
    RECENT_OUTPUT_LINES = 5            # Number of lines to display

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize background process notification service.

        Args:
            connection_manager: WebSocket connection manager instance
        """
        self.connection_manager = connection_manager
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}  # process_id -> monitoring task

    async def start_monitoring(
        self,
        session_id: str,
        process_id: str,
        command: str,
        description: Optional[str] = None
    ) -> None:
        """
        Start monitoring a background process and send notifications.

        Sends initial STARTED notification and begins monitoring loop
        for output updates.

        Args:
            session_id: WebSocket session ID
            process_id: Background process ID
            command: Shell command being executed
            description: Optional command description
        """
        # Import here to avoid circular dependency
        from backend.infrastructure.shell.background_process_manager import get_process_manager

        # Send initial STARTED notification
        await self._send_notification(
            session_id=session_id,
            process_id=process_id,
            command=command,
            description=description,
            status="running",
            message_type=MessageType.BACKGROUND_PROCESS_STARTED,
            recent_output=[],
            runtime_seconds=0.0
        )

        # Create monitoring task
        async def monitor_loop():
            """Async monitoring loop for process output."""
            process_manager = get_process_manager()

            try:
                while True:
                    # Get process object
                    process = process_manager.processes.get(process_id)
                    if not process:
                        logger.warning(f"Process {process_id} not found in manager, stopping monitoring")
                        break

                    # Check if process completed
                    if process.status == "running" and process.process.poll() is not None:
                        process.status = "completed"
                        process.exit_code = process.process.returncode

                    # Get output info under lock
                    with process._output_lock:
                        total_lines = len(process.stdout_buffer) + len(process.stderr_buffer)
                        recent_lines = self._get_recent_lines(process)

                    # Calculate runtime
                    runtime = (datetime.now() - process.start_time).total_seconds()

                    # Determine message type
                    if process.status == "completed":
                        msg_type = MessageType.BACKGROUND_PROCESS_COMPLETED
                    elif process.status == "killed":
                        msg_type = MessageType.BACKGROUND_PROCESS_KILLED
                    else:
                        msg_type = MessageType.BACKGROUND_PROCESS_OUTPUT_UPDATE

                    # Check if there's more output beyond what we're showing
                    has_more = total_lines > self.RECENT_OUTPUT_LINES

                    await self._send_notification(
                        session_id=session_id,
                        process_id=process_id,
                        command=command,
                        description=description,
                        status=process.status,
                        message_type=msg_type,
                        recent_output=recent_lines,
                        runtime_seconds=runtime,
                        has_more_output=has_more,
                        exit_code=process.exit_code
                    )

                    # Stop monitoring if process completed/killed
                    if process.status in ["completed", "killed"]:
                        logger.info(f"Process {process_id} {process.status}, stopping monitoring")
                        break

                    # Wait before next check
                    await asyncio.sleep(self.NOTIFICATION_INTERVAL_SECONDS)

            except Exception as e:
                logger.error(f"Error monitoring process {process_id}: {e}", exc_info=True)
            finally:
                # Cleanup
                if process_id in self._monitoring_tasks:
                    del self._monitoring_tasks[process_id]

        # Start monitoring task
        task = asyncio.create_task(monitor_loop())
        self._monitoring_tasks[process_id] = task
        logger.info(f"Started monitoring process {process_id}")

    def _get_recent_lines(self, process) -> List[str]:
        """
        Get the most recent output lines (last 5 lines) from process.

        Combines stdout and stderr, prioritizing the most recent output.

        Args:
            process: BackgroundProcess object

        Returns:
            List of most recent output lines (max 5 lines)
        """
        # Already have lock from caller
        stdout_buffer = process.stdout_buffer
        stderr_buffer = process.stderr_buffer

        # Simple strategy: Mix stdout and stderr, showing most recent
        # Priority: If stderr has content, show it; otherwise show stdout
        all_lines = []

        # Get last N lines from each buffer
        recent_stdout = stdout_buffer[-self.RECENT_OUTPUT_LINES:] if stdout_buffer else []
        recent_stderr = stderr_buffer[-self.RECENT_OUTPUT_LINES:] if stderr_buffer else []

        # If we have stderr (usually errors/warnings), prioritize it
        if recent_stderr:
            # Show some stderr and some stdout for context
            stderr_count = min(3, len(recent_stderr))
            stdout_count = self.RECENT_OUTPUT_LINES - stderr_count

            all_lines.extend(recent_stderr[-stderr_count:])
            all_lines.extend(recent_stdout[-stdout_count:])
        else:
            # Only stdout
            all_lines = recent_stdout[-self.RECENT_OUTPUT_LINES:]

        return all_lines[-self.RECENT_OUTPUT_LINES:]  # Ensure max 5 lines

    async def _send_notification(
        self,
        session_id: str,
        process_id: str,
        command: str,
        status: str,
        message_type: MessageType,
        recent_output: List[str],
        runtime_seconds: float,
        description: Optional[str] = None,
        has_more_output: bool = False,
        exit_code: Optional[int] = None
    ) -> None:
        """
        Send background process notification to frontend.

        Args:
            session_id: WebSocket session ID
            process_id: Process ID
            command: Shell command
            status: Process status
            message_type: Notification type
            recent_output: Recent output lines
            runtime_seconds: Process runtime
            description: Optional description
            has_more_output: Whether more output is available
            exit_code: Exit code if completed/killed
        """
        notification = create_message(
            message_type,
            process_id=process_id,
            command=command,
            status=status,
            recent_output=recent_output,
            runtime_seconds=runtime_seconds,
            description=description,
            has_more_output=has_more_output,
            exit_code=exit_code,
            session_id=session_id
        ).model_dump(mode="json", exclude_none=True)

        # Send via WebSocket
        if await self.connection_manager.is_connected(session_id):
            await self.connection_manager.send_json(session_id, notification)
            logger.debug(f"Sent {message_type} notification for process {process_id}")
        else:
            logger.warning(f"Session {session_id} not connected, cannot send notification for process {process_id}")

    def stop_monitoring(self, process_id: str) -> None:
        """
        Stop monitoring a background process.

        Args:
            process_id: Process ID to stop monitoring
        """
        task = self._monitoring_tasks.get(process_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled monitoring for process {process_id}")

        # Cleanup
        if process_id in self._monitoring_tasks:
            del self._monitoring_tasks[process_id]

    def cleanup_session(self, session_id: str) -> None:
        """
        Stop all monitoring tasks for a session.

        Args:
            session_id: Session ID to cleanup
        """
        # Note: We don't track session_id to process_id mapping here
        # The BackgroundProcessManager handles session cleanup
        # This is called when session disconnects to stop any lingering tasks
        tasks_to_cancel = list(self._monitoring_tasks.values())
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()

        logger.info(f"Cleaned up background process monitoring for session {session_id}")


def get_background_process_notification_service() -> Optional[BackgroundProcessNotificationService]:
    """
    Get background process notification service from WebSocketHandler.

    Returns:
        BackgroundProcessNotificationService instance or None if not initialized

    Note:
        The service is initialized and managed by WebSocketHandler,
        avoiding global state and ensuring proper lifecycle management.
    """
    try:
        from backend.shared.utils.app_context import get_app

        app = get_app()
        if not app:
            logger.warning("FastAPI app not initialized")
            return None

        if not hasattr(app.state, 'websocket_handler'):
            logger.warning("WebSocket handler not found in app state")
            return None

        handler = app.state.websocket_handler
        if not hasattr(handler, 'background_process_notification_service'):
            logger.warning("Background process notification service not found in WebSocket handler")
            return None

        return handler.background_process_notification_service

    except Exception as e:
        logger.warning(f"Could not get background process notification service: {e}")
        return None
