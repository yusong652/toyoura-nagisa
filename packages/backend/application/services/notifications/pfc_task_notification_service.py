"""
PFC Task Notification Service - DDD Application Layer

This service manages real-time notifications for PFC background tasks,
coordinating between the PFC WebSocket client and frontend WebSocket.

DDD Role: Application Service
- Polls PFC server for task status updates
- Pushes real-time output for running tasks to frontend
- Handles task lifecycle notifications

Note: PFC only supports single-task execution, so this service
monitors one active task at a time.
"""
import asyncio
import logging
from typing import Dict, Optional, List, Any

from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.messages.types import MessageType
from backend.presentation.websocket.messages.factory import create_message

logger = logging.getLogger(__name__)


class PfcTaskNotificationService:
    """
    Application Service for PFC Task Notifications.

    Polls PFC server for task status and sends real-time updates to frontend
    via WebSocket. Each session has one polling loop that monitors the active task.

    Architecture:
    - One async polling loop per session
    - Polls list_tasks() to get current task status
    - Calls check_task_status() for running tasks to get output
    - Automatically stops when no running task exists
    """

    # Configuration
    POLLING_INTERVAL_SECONDS = 2.0   # Poll interval (seconds)
    RECENT_OUTPUT_LINES = 10         # Number of output lines to display

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize PFC task notification service.

        Args:
            connection_manager: WebSocket connection manager instance
        """
        self.connection_manager = connection_manager
        self._polling_tasks: Dict[str, asyncio.Task] = {}  # session_id -> polling task
        self._last_task_id: Dict[str, Optional[str]] = {}  # session_id -> last task_id for state change detection

    async def start_polling(self, session_id: str) -> None:
        """
        Start polling for a session (if not already running).

        Called when pfc_execute_task with run_in_background=True succeeds.
        Only one polling task runs per session.

        Args:
            session_id: Session ID to poll for
        """
        # Already polling for this session
        if session_id in self._polling_tasks:
            task = self._polling_tasks[session_id]
            if not task.done():
                logger.debug(f"Polling already active for session {session_id}")
                return

        # Start polling task
        task = asyncio.create_task(self._polling_loop(session_id))
        self._polling_tasks[session_id] = task
        logger.info(f"Started PFC task polling for session {session_id}")

    async def _polling_loop(self, session_id: str) -> None:
        """
        Main polling loop for a session.

        Polls PFC server for task status and pushes updates to frontend.
        Automatically stops when no running task exists.

        Args:
            session_id: Session ID to poll for
        """
        from backend.infrastructure.pfc import get_pfc_client

        try:
            consecutive_empty = 0  # Count consecutive polls with no running task

            while True:
                try:
                    # Get PFC client
                    client = await get_pfc_client()

                    # Query tasks for this session
                    result = await client.list_tasks(
                        session_id=session_id,
                        limit=5
                    )

                    if result.get("status") != "success":
                        logger.warning(f"Failed to list PFC tasks: {result.get('message')}")
                        await asyncio.sleep(self.POLLING_INTERVAL_SECONDS)
                        continue

                    tasks = result.get("data", [])

                    # Find running task (PFC only supports single task)
                    running_task = next(
                        (t for t in tasks if t.get("status") == "running"),
                        None
                    )

                    # Track last task to detect state changes
                    last_task_id = self._last_task_id.get(session_id)

                    if running_task:
                        consecutive_empty = 0
                        self._last_task_id[session_id] = running_task.get("task_id")
                        await self._process_running_task(session_id, running_task, client)
                    else:
                        # No running task - check if previous task completed/failed/interrupted
                        if last_task_id:
                            # Find the completed task
                            completed_task = next(
                                (t for t in tasks if t.get("task_id") == last_task_id),
                                None
                            )
                            if completed_task:
                                await self._send_final_status(session_id, completed_task, client)
                            self._last_task_id[session_id] = None

                        consecutive_empty += 1
                        if consecutive_empty >= 2:
                            logger.info(f"No running PFC task for session {session_id}, stopping polling")
                            break

                    await asyncio.sleep(self.POLLING_INTERVAL_SECONDS)

                except ConnectionError as e:
                    logger.warning(f"PFC connection error during polling: {e}")
                    await asyncio.sleep(self.POLLING_INTERVAL_SECONDS)

                except Exception as e:
                    logger.error(f"Error in PFC polling loop: {e}", exc_info=True)
                    await asyncio.sleep(self.POLLING_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            logger.debug(f"PFC polling cancelled for session {session_id}")

        finally:
            self._cleanup_session(session_id)

    async def _process_running_task(
        self,
        session_id: str,
        task_info: Dict[str, Any],
        client: Any
    ) -> None:
        """
        Process a running task - get output and push update.

        Args:
            session_id: Session ID
            task_info: Task info from list_tasks
            client: PFC WebSocket client
        """
        task_id = task_info.get("task_id")
        if not task_id:
            return

        try:
            # Get detailed status with output
            status_result = await client.check_task_status(task_id)

            if status_result.get("status") == "not_found":
                logger.warning(f"Task {task_id} not found")
                return

            # Extract data
            data = status_result.get("data", {})
            current_output = data.get("current_output") or data.get("output") or ""
            elapsed_time = data.get("elapsed_time", 0)

            # Get recent lines
            recent_lines = self._get_recent_lines(current_output)
            total_lines = len(current_output.split('\n')) if current_output else 0

            # Send notification using create_message
            notification = create_message(
                MessageType.PFC_TASK_UPDATE,
                task_id=task_id,
                session_id=session_id,
                script_name=task_info.get("name", ""),
                entry_script=task_info.get("entry_script", ""),
                description=task_info.get("description", ""),
                status="running",
                source=task_info.get("source", "agent"),
                git_commit=task_info.get("git_commit"),
                start_time=task_info.get("start_time"),
                elapsed_time=elapsed_time,
                recent_output=recent_lines,
                has_more_output=total_lines > self.RECENT_OUTPUT_LINES
            )

            await self._send_notification(session_id, notification)

        except Exception as e:
            logger.error(f"Error processing running task {task_id}: {e}")

    async def _send_final_status(
        self,
        session_id: str,
        task_info: Dict[str, Any],
        client: Any
    ) -> None:
        """
        Send final status notification when task completes/fails/interrupts.

        Args:
            session_id: Session ID
            task_info: Task info from list_tasks
            client: PFC WebSocket client
        """
        task_id = task_info.get("task_id")
        if not task_id:
            return

        try:
            # Get detailed status with final output
            status_result = await client.check_task_status(task_id)

            if status_result.get("status") == "not_found":
                logger.warning(f"Task {task_id} not found for final status")
                return

            # Extract data
            data = status_result.get("data", {})
            current_output = data.get("current_output") or data.get("output") or ""
            elapsed_time = data.get("elapsed_time", 0)
            error = data.get("error")

            # Get recent lines
            recent_lines = self._get_recent_lines(current_output)
            total_lines = len(current_output.split('\n')) if current_output else 0

            # Map status
            status = task_info.get("status", "completed")

            # Send final notification
            notification = create_message(
                MessageType.PFC_TASK_UPDATE,
                task_id=task_id,
                session_id=session_id,
                script_name=task_info.get("name", ""),
                entry_script=task_info.get("entry_script", ""),
                description=task_info.get("description", ""),
                status=status,
                source=task_info.get("source", "agent"),
                git_commit=task_info.get("git_commit"),
                start_time=task_info.get("start_time"),
                elapsed_time=elapsed_time,
                recent_output=recent_lines,
                has_more_output=total_lines > self.RECENT_OUTPUT_LINES,
                error=error
            )

            await self._send_notification(session_id, notification)
            logger.info(f"Sent final status '{status}' for task {task_id}")

        except Exception as e:
            logger.error(f"Error sending final status for task {task_id}: {e}")

    async def _send_notification(
        self,
        session_id: str,
        notification: Any
    ) -> None:
        """
        Send notification via WebSocket.

        Args:
            session_id: Session ID
            notification: Message object to send
        """
        if await self.connection_manager.is_connected(session_id):
            await self.connection_manager.send_json(
                session_id,
                notification.model_dump(mode="json", exclude_none=True)
            )
            logger.debug(f"Sent PFC task update for session {session_id}")
        else:
            logger.debug(f"Session {session_id} not connected, skipping notification")

    def _get_recent_lines(self, output: str) -> List[str]:
        """
        Get the most recent output lines.

        Args:
            output: Full output string

        Returns:
            List of most recent output lines
        """
        if not output:
            return []

        lines = output.strip().split('\n')
        return lines[-self.RECENT_OUTPUT_LINES:]

    def stop_polling(self, session_id: str) -> None:
        """
        Stop polling for a session.

        Args:
            session_id: Session ID to stop polling for
        """
        task = self._polling_tasks.get(session_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled PFC polling for session {session_id}")

        self._cleanup_session(session_id)

    def _cleanup_session(self, session_id: str) -> None:
        """
        Clean up session state.

        Args:
            session_id: Session ID to clean up
        """
        if session_id in self._polling_tasks:
            del self._polling_tasks[session_id]
        if session_id in self._last_task_id:
            del self._last_task_id[session_id]

    def cleanup_all(self) -> None:
        """Stop all polling tasks (for shutdown)."""
        for session_id in list(self._polling_tasks.keys()):
            self.stop_polling(session_id)
        logger.info("Cleaned up all PFC task polling")


def get_pfc_task_notification_service() -> Optional["PfcTaskNotificationService"]:
    """
    Get PFC task notification service from WebSocketHandler.

    Returns:
        PfcTaskNotificationService instance or None if not initialized

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
        if not hasattr(handler, 'pfc_task_notification_service'):
            logger.warning("PFC task notification service not found in WebSocket handler")
            return None

        return handler.pfc_task_notification_service

    except Exception as e:
        logger.warning(f"Could not get PFC task notification service: {e}")
        return None
