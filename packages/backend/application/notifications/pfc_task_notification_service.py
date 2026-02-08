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
import os
import re
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
        - Polls PFC server for task status via MCP
        - Sends real-time updates to frontend via WebSocket
        - Signals foreground handles when their tasks complete

        Stops when no running task AND no active foreground handle for this session.

        Args:
            session_id: Session ID to poll for
        """
        from backend.infrastructure.pfc.task_manager import get_pfc_task_manager

        try:
            consecutive_empty = 0  # Count consecutive polls with no running task
            task_manager = get_pfc_task_manager()

            while True:
                try:
                    # Get foreground task_ids for this session (for proactive completion check)
                    fg_task_ids = {
                        ctx.task_id for ctx in self._foreground_contexts.values()
                        if ctx.session_id == session_id
                    }
                    has_foreground = len(fg_task_ids) > 0

                    # Get tasks from local task manager
                    local_tasks = task_manager.list_tasks(session_id=session_id, limit=5)
                    tasks = [
                        {
                            "task_id": t.task_id,
                            "bridge_task_id": t.bridge_task_id,
                            "status": t.status,
                            "name": os.path.basename(t.script_path),
                            "entry_script": t.script_path,
                            "description": t.description,
                            "source": t.source,
                            "git_commit": t.git_commit,
                            "start_time": t.start_time.timestamp() if t.start_time else None,
                            "end_time": t.end_time.timestamp() if t.end_time else None,
                        }
                        for t in local_tasks
                    ]

                    # Find active task (PFC only supports single task)
                    running_task = next(
                        (
                            t
                            for t in tasks
                            if t.get("status") in ("pending", "submitted", "running")
                        ),
                        None
                    )

                    # Track last task to detect state changes
                    last_task_id = self._last_task_id.get(session_id)

                    if running_task:
                        consecutive_empty = 0
                        self._last_task_id[session_id] = running_task.get("task_id")
                        await self._process_running_task(session_id, running_task)
                    else:
                        # No running task - check completions
                        handled_task_ids = set()

                        # 1. Check foreground tasks proactively (handles fast-completing tasks)
                        for task in tasks:
                            task_id = task.get("task_id")
                            status = task.get("status")
                            if task_id in fg_task_ids and status not in ("running", "pending"):
                                await self._handle_task_completion(session_id, task)
                                handled_task_ids.add(task_id)

                        # 2. Check last_task_id for background tasks (original logic)
                        if last_task_id and last_task_id not in handled_task_ids:
                            completed_task = next(
                                (t for t in tasks if t.get("task_id") == last_task_id),
                                None
                            )
                            if completed_task:
                                await self._handle_task_completion(session_id, completed_task)

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
    ) -> None:
        """
        Process a running task - get output, update foreground handle, and optionally push to frontend.

        For foreground tasks: only update handle (no frontend notification, like bash)
        For background tasks: send frontend notification

        Args:
            session_id: Session ID
            task_info: Task info from local task manager
        """
        task_id = task_info.get("task_id")
        if not task_id:
            return

        try:
            # Sync latest status/output from MCP first
            sync_result = await self._sync_task_from_mcp(task_info)
            if sync_result and sync_result.get("is_terminal"):
                await self._handle_task_completion(session_id, task_info)
                return

            # Get detailed output from local task manager
            from backend.infrastructure.pfc.task_manager import get_pfc_task_manager
            task_manager = get_pfc_task_manager()
            task = task_manager.get_task(task_id)
            if not task:
                return

            current_output = "\n".join(task.output_lines) if task.output_lines else ""
            elapsed_time = task.elapsed_seconds

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
    ) -> None:
        """
        Handle task completion - signal foreground handle and send frontend notification.

        This is the unified completion handler for both foreground and background tasks:
        - For foreground: signals the handle to unblock pfc_execute_task.wait()
        - For all tasks: sends final status notification to frontend

        Args:
            session_id: Session ID
            task_info: Task info from local task manager
        """
        task_id = task_info.get("task_id")
        if not task_id:
            return

        try:
            # Get data from local task manager (already synced)
            from backend.infrastructure.pfc.task_manager import get_pfc_task_manager
            task_manager = get_pfc_task_manager()
            task = task_manager.get_task(task_id)
            if not task:
                return

            current_output = "\n".join(task.output_lines) if task.output_lines else ""
            elapsed_time = task.elapsed_seconds
            error = task.error
            result = task.result
            git_commit = task.git_commit

            mapped_status = task.status

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
                    start_time=task_info.get("start_time"),
                    end_time=task_info.get("end_time"),
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

    async def _sync_task_from_mcp(self, task_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sync local task state from pfc_check_task_status MCP result."""
        local_task_id = task_info.get("task_id")
        if not local_task_id:
            return None

        remote_task_id = task_info.get("bridge_task_id") or local_task_id

        try:
            from backend.infrastructure.mcp.client import get_mcp_client_manager
            from backend.infrastructure.pfc.task_manager import get_pfc_task_manager
            from backend.shared.utils.mcp_utils import extract_mcp_text

            mcp_manager = get_mcp_client_manager()
            status_result = await mcp_manager.call_tool(
                "pfc_check_task_status",
                {
                    "task_id": remote_task_id,
                    "wait_seconds": 1,
                    "limit": 200,
                    "skip_newest": 0,
                },
            )

            if status_result.get("status") == "error":
                logger.warning(
                    "pfc_check_task_status failed for local=%s remote=%s: %s",
                    local_task_id,
                    remote_task_id,
                    status_result.get("message", "unknown error"),
                )
                return None

            parsed = self._parse_task_status_text(extract_mcp_text(status_result))
            if not parsed:
                return None

            normalized_status = parsed["status"]
            if normalized_status == "not_found":
                # If bridge_task_id was never captured, avoid false failure on local task id mismatch.
                if not task_info.get("bridge_task_id"):
                    logger.warning(
                        "Skipping not_found sync for local=%s because bridge_task_id is missing",
                        local_task_id,
                    )
                    return None
                normalized_status = "failed"
                parsed["error"] = parsed.get("error") or "Remote task not found on pfc-bridge"

            task_manager = get_pfc_task_manager()
            task_manager.update_status(
                local_task_id,
                normalized_status,
                error=parsed.get("error"),
                result=parsed.get("result"),
            )

            output = parsed.get("output")
            if isinstance(output, str):
                task_manager.set_output(local_task_id, output)

            return {
                "status": normalized_status,
                "is_terminal": normalized_status in ("completed", "failed", "interrupted"),
            }

        except Exception as e:
            logger.warning(
                "Failed to sync task status from MCP for local=%s remote=%s: %s",
                local_task_id,
                remote_task_id,
                e,
            )
            return None

    def _parse_task_status_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse pfc_check_task_status textual response."""
        if not text:
            return None

        status = "running"
        error: Optional[str] = None
        result: Optional[str] = None
        output_lines: List[str] = []
        in_output = False

        for raw_line in text.splitlines():
            line = raw_line.rstrip("\r")
            stripped = line.strip()
            lowered = stripped.lower()

            if lowered.startswith("- status:"):
                raw_status = stripped.split(":", 1)[1].strip().lower()
                status = self._normalize_status(raw_status)
                continue

            if lowered.startswith("- error:"):
                candidate = stripped.split(":", 1)[1].strip()
                if candidate and candidate.lower() not in {"none", "n/a"}:
                    error = candidate
                continue

            if lowered.startswith("- result:"):
                candidate = stripped.split(":", 1)[1].strip()
                if candidate and candidate.lower() not in {"none", "n/a"}:
                    result = candidate
                continue

            if lowered.startswith("output ") or stripped == "Output:" or "=== Script Output" in line:
                in_output = True
                continue

            if in_output and lowered.startswith("next:"):
                break

            if in_output:
                output_lines.append(line)

        output_text = "\n".join(output_lines).strip()
        if output_text == "(no output)":
            output_text = ""

        return {
            "status": status,
            "error": error,
            "result": result,
            "output": output_text,
        }

    def _normalize_status(self, status: str) -> str:
        """Normalize bridge/MCP task status into local task status."""
        status = (status or "").strip().lower()
        if status in {"success", "completed"}:
            return "completed"
        if status in {"error", "failed"}:
            return "failed"
        if status == "interrupted":
            return "interrupted"
        if status == "pending":
            return "pending"
        if status in {"running", "submitted"}:
            return "running"
        if status == "not_found":
            return "not_found"

        if re.search(r"\b(success|completed)\b", status):
            return "completed"
        if re.search(r"\b(error|failed)\b", status):
            return "failed"
        return "running"

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
        Queries pfc-bridge for latest output to provide complete status.

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
        script_name = os.path.basename(script_path)

        # Get latest output from local task manager
        recent_lines: List[str] = []
        has_more = False
        actual_elapsed = elapsed_seconds

        try:
            from backend.infrastructure.pfc.task_manager import get_pfc_task_manager
            task_manager = get_pfc_task_manager()
            task = task_manager.get_task(task_id)
            if task:
                current_output = "\n".join(task.output_lines) if task.output_lines else ""
                actual_elapsed = task.elapsed_seconds
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
