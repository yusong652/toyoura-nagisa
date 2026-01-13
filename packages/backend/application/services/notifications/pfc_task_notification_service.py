"""
PFC Task Notification Service - DDD Application Layer

This service manages real-time notifications for PFC tasks (both foreground and background),
coordinating between the PFC WebSocket client, frontend WebSocket, and foreground handles.

DDD Role: Application Service
- Unified polling loop for both foreground and background tasks
- Pushes real-time output to frontend via WebSocket
- Signals foreground handles when tasks complete
- Handles task lifecycle notifications

Note: PFC only supports single-task execution, so this service
monitors one active task at a time.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, List, Any, TYPE_CHECKING

from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.messages.types import MessageType
from backend.presentation.websocket.messages.factory import create_message

if TYPE_CHECKING:
    from backend.infrastructure.pfc.foreground_handle import PfcForegroundExecutionHandle

logger = logging.getLogger(__name__)


@dataclass
class ForegroundTaskContext:
    """Context for a foreground task being polled."""
    task_id: str
    session_id: str
    script_path: str
    description: str
    git_commit: Optional[str]
    handle: "PfcForegroundExecutionHandle"
    start_time: float  # time.time() when registered


class PfcTaskNotificationService:
    """
    Application Service for PFC Task Notifications.

    Unified polling service for both foreground and background PFC tasks:
    - Polls PFC server for task status updates
    - Sends real-time output to frontend via WebSocket
    - Signals foreground handles when their tasks complete

    Architecture:
    - One async polling loop per session
    - Tracks foreground handles for completion signaling
    - Automatically stops when no running task and no foreground handle
    """

    # Configuration
    POLLING_INTERVAL_SECONDS = 1.0   # Poll interval (seconds)
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

        # Foreground handle tracking (by task_id for completion signaling)
        self._foreground_contexts: Dict[str, ForegroundTaskContext] = {}  # task_id -> context

    def register_foreground_handle(
        self,
        task_id: str,
        session_id: str,
        script_path: str,
        description: str,
        git_commit: Optional[str],
        handle: "PfcForegroundExecutionHandle",
    ) -> None:
        """
        Register a foreground handle for completion signaling.

        Called by pfc_execute_task when starting foreground execution.
        The polling loop will signal this handle when the task completes.

        Args:
            task_id: PFC task ID
            session_id: WebSocket session ID
            script_path: Path to entry script
            description: Task description
            git_commit: Git commit hash (if any)
            handle: Foreground execution handle to signal
        """
        self._foreground_contexts[task_id] = ForegroundTaskContext(
            task_id=task_id,
            session_id=session_id,
            script_path=script_path,
            description=description,
            git_commit=git_commit,
            handle=handle,
            start_time=time.time(),
        )
        logger.debug(f"Registered foreground handle for task {task_id}")

    def unregister_foreground_handle(self, task_id: str) -> None:
        """
        Unregister a foreground handle.

        Called when foreground wait completes or is cancelled.

        Args:
            task_id: PFC task ID
        """
        if task_id in self._foreground_contexts:
            del self._foreground_contexts[task_id]
            logger.debug(f"Unregistered foreground handle for task {task_id}")

    def get_foreground_context(self, task_id: str) -> Optional[ForegroundTaskContext]:
        """
        Get foreground context for a task.

        Args:
            task_id: PFC task ID

        Returns:
            ForegroundTaskContext if task has a registered foreground handle
        """
        return self._foreground_contexts.get(task_id)

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

        Unified polling for both foreground and background tasks:
        - Polls PFC server for task status
        - Sends real-time updates to frontend via WebSocket
        - Signals foreground handles when their tasks complete

        Stops when no running task AND no active foreground handle for this session.

        Args:
            session_id: Session ID to poll for
        """
        from backend.infrastructure.pfc import get_pfc_client

        try:
            consecutive_empty = 0  # Count consecutive polls with no running task

            while True:
                try:
                    # Get foreground task_ids for this session (for proactive completion check)
                    # This handles fast-completing tasks that finish before first poll
                    fg_task_ids = {
                        ctx.task_id for ctx in self._foreground_contexts.values()
                        if ctx.session_id == session_id
                    }
                    has_foreground = len(fg_task_ids) > 0

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
                        # No running task - check completions
                        handled_task_ids = set()

                        # 1. Check foreground tasks proactively (handles fast-completing tasks)
                        # These tasks may have completed before we ever saw them as "running"
                        for task in tasks:
                            task_id = task.get("task_id")
                            status = task.get("status")
                            if task_id in fg_task_ids and status not in ("running", "pending"):
                                await self._handle_task_completion(session_id, task, client)
                                handled_task_ids.add(task_id)

                        # 2. Check last_task_id for background tasks (original logic)
                        if last_task_id and last_task_id not in handled_task_ids:
                            completed_task = next(
                                (t for t in tasks if t.get("task_id") == last_task_id),
                                None
                            )
                            if completed_task:
                                await self._handle_task_completion(session_id, completed_task, client)

                        self._last_task_id[session_id] = None
                        consecutive_empty += 1

                        # Stop only if no running task AND no foreground handle waiting
                        if consecutive_empty >= 2 and not has_foreground:
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
        Process a running task - get output, update foreground handle, and optionally push to frontend.

        For foreground tasks: only update handle (no frontend notification, like bash)
        For background tasks: send frontend notification

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

            # Check if this is a foreground task
            fg_ctx = self._foreground_contexts.get(task_id)

            if fg_ctx:
                # Foreground task: only update handle, NO frontend notification (like bash)
                fg_ctx.handle.update_elapsed(elapsed_time)
                return

            # Background task: send frontend notification
            recent_lines = self._get_recent_lines(current_output)
            total_lines = len(current_output.split('\n')) if current_output else 0

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
                has_more_output=total_lines > self.RECENT_OUTPUT_LINES,
            )

            await self._send_notification(session_id, notification)

        except Exception as e:
            logger.error(f"Error processing running task {task_id}: {e}")

    async def _handle_task_completion(
        self,
        session_id: str,
        task_info: Dict[str, Any],
        client: Any
    ) -> None:
        """
        Handle task completion - signal foreground handle and send frontend notification.

        This is the unified completion handler for both foreground and background tasks:
        - For foreground: signals the handle to unblock pfc_execute_task.wait()
        - For all tasks: sends final status notification to frontend

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
            result = data.get("result")
            git_commit = task_info.get("git_commit") or data.get("git_commit")

            # Map server status to display status
            server_status = task_info.get("status", "completed")
            status_map = {
                "success": "completed",
                "error": "failed",
                "interrupted": "interrupted",
            }
            mapped_status = status_map.get(server_status, server_status)

            # Get recent lines
            recent_lines = self._get_recent_lines(current_output)
            total_lines = len(current_output.split('\n')) if current_output else 0

            # Check if this is a foreground task
            fg_ctx = self._foreground_contexts.get(task_id)

            if fg_ctx:
                # Foreground task: signal handle, NO frontend notification (like bash)
                fg_ctx.handle.signal_completion(
                    status=mapped_status,
                    output=current_output,
                    elapsed_seconds=elapsed_time,
                    result=result,
                    error=error,
                    git_commit=git_commit,
                )
                logger.info(f"Signaled foreground handle completion for task {task_id}: status={mapped_status}")
                return

            # Background task: send final notification to frontend
            notification = create_message(
                MessageType.PFC_TASK_UPDATE,
                task_id=task_id,
                session_id=session_id,
                script_name=task_info.get("name", ""),
                entry_script=task_info.get("entry_script", ""),
                description=task_info.get("description", ""),
                status=mapped_status,
                source=task_info.get("source", "agent"),
                git_commit=git_commit,
                start_time=task_info.get("start_time"),
                elapsed_time=elapsed_time,
                recent_output=recent_lines,
                has_more_output=total_lines > self.RECENT_OUTPUT_LINES,
                error=error,
                result=str(result) if result else None,
            )

            await self._send_notification(session_id, notification)
            logger.info(f"Sent final status '{mapped_status}' for task {task_id}")

        except Exception as e:
            logger.error(f"Error handling task completion for {task_id}: {e}")

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

    # ===== Foreground Task Notification Methods =====
    # These are called directly by pfc_execute_task tool for specific events

    async def notify_foreground_started(
        self,
        session_id: str,
        task_id: str,
        script_path: str,
        description: Optional[str] = None,
        git_commit: Optional[str] = None,
    ) -> None:
        """
        Send notification when foreground PFC task starts running.

        Called by pfc_execute_task when task is submitted in foreground mode.
        Subsequent updates are handled by the unified polling loop.

        Args:
            session_id: WebSocket session ID
            task_id: PFC task ID
            script_path: Path to entry script
            description: Optional task description
            git_commit: Optional git commit hash
        """
        import os
        script_name = os.path.basename(script_path)

        notification = create_message(
            MessageType.PFC_TASK_UPDATE,
            task_id=task_id,
            session_id=session_id,
            script_name=script_name,
            entry_script=script_path,
            description=description or "",
            status="running",
            source="agent",
            git_commit=git_commit,
            elapsed_time=0.0,
            recent_output=[],
            has_more_output=False,
            is_foreground=True,
        )

        await self._send_notification(session_id, notification)
        logger.debug(f"Sent foreground started notification for task {task_id}")

    async def notify_foreground_backgrounded(
        self,
        session_id: str,
        task_id: str,
        script_path: str,
        reason: str,
        elapsed_seconds: float,
        description: Optional[str] = None,
        git_commit: Optional[str] = None,
        source: str = "agent",
    ) -> None:
        """
        Send notification when foreground task is moved to background (ctrl+b or timeout).

        This is the FIRST frontend notification for this task (foreground mode has no UI).
        Queries pfc-server for latest output to provide complete status.

        Args:
            session_id: WebSocket session ID
            task_id: PFC task ID
            script_path: Path to entry script
            reason: Reason for backgrounding ("user_request" or "timeout")
            elapsed_seconds: Task runtime at backgrounding
            description: Optional task description
            git_commit: Optional git commit hash
            source: Task source ("agent" or "user_console")
        """
        import os
        from backend.infrastructure.pfc import get_pfc_client

        script_name = os.path.basename(script_path)

        # Query pfc-server for latest output (first notification needs complete data)
        recent_lines: List[str] = []
        has_more = False
        actual_elapsed = elapsed_seconds

        try:
            client = await get_pfc_client()
            status_result = await client.check_task_status(task_id)
            if status_result.get("status") not in ("not_found", "error"):
                data = status_result.get("data", {})
                current_output = data.get("current_output") or data.get("output") or ""
                actual_elapsed = data.get("elapsed_time", elapsed_seconds)
                recent_lines = self._get_recent_lines(current_output)
                total_lines = len(current_output.split('\n')) if current_output else 0
                has_more = total_lines > self.RECENT_OUTPUT_LINES
        except Exception as e:
            logger.warning(f"Failed to get latest output for backgrounded task {task_id}: {e}")

        notification = create_message(
            MessageType.PFC_TASK_UPDATE,
            task_id=task_id,
            session_id=session_id,
            script_name=script_name,
            entry_script=script_path,
            description=description or "",
            status="backgrounded",
            source=source,
            git_commit=git_commit,
            elapsed_time=actual_elapsed,
            recent_output=recent_lines,
            has_more_output=has_more,
            is_foreground=False,
            background_reason=reason,
        )

        await self._send_notification(session_id, notification)
        logger.info(f"Sent backgrounded notification for task {task_id}: source={source}, reason={reason}")

    # Note: notify_foreground_completed is no longer needed - completion is handled
    # by the unified polling loop via _handle_task_completion()

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
