"""
PFC WebSocket Client - Connects toyoura-nagisa backend to PFC server.

This client maintains a WebSocket connection to the PFC server running
in the PFC GUI IPython shell, enabling real-time command execution.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Union
from uuid import uuid4
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

logger = logging.getLogger("PFC-Client")


class PFCWebSocketClient:
    """WebSocket client for communicating with PFC server.

    Script-only workflow: All PFC operations are executed through Python scripts.
    Direct command execution is not supported.
    """

    def __init__(
        self,
        url: str = "ws://localhost:9001",
        auto_reconnect: bool = True,
        reconnect_interval: float = 2.0,
        max_reconnect_attempts: int = 0
    ):
        """
        Initialize PFC WebSocket client.

        Args:
            url: WebSocket server URL (default: ws://localhost:9001)
            auto_reconnect: Enable automatic reconnection on connection loss (default: True)
            reconnect_interval: Seconds between reconnection attempts (default: 2.0)
            max_reconnect_attempts: Maximum consecutive reconnect attempts (0 = unlimited, default: 0)
        """
        self.url = url
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts

        self._websocket: Optional[Any] = None
        self.connected = False
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._message_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnecting = False
        self._reconnect_count = 0
        self._lock = asyncio.Lock()
        self._should_stop = False

    @property
    def websocket(self) -> Any:
        """
        Get websocket connection, ensuring it exists.

        Returns:
            WebSocket connection object

        Raises:
            RuntimeError: If accessed before connection established
        """
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected. Call connect() first.")
        return self._websocket

    async def _ensure_connected(self):
        """
        Ensure WebSocket is connected, waiting for reconnection if needed.

        This method handles:
        1. Waiting for auto-reconnect if in progress
        2. Manual reconnection if not connected

        Raises:
            ConnectionError: If connection cannot be established
        """
        # Wait for reconnection if in progress
        if self._reconnecting:
            logger.info("Waiting for auto-reconnect to complete...")
            for _ in range(60):  # 60 * 0.5s = 30s max wait
                if not self._reconnecting and self.connected:
                    break
                await asyncio.sleep(0.5)

            if not self.connected:
                raise ConnectionError("Auto-reconnect did not complete in time")

        # Ensure connected (manual reconnect if needed)
        if not self.connected:
            self._should_stop = False  # Allow reconnection
            success = await self.connect()
            if not success:
                raise ConnectionError("Failed to connect to PFC server")

    async def _send_request(
        self,
        message: Dict[str, Any],
        timeout: float,
        operation_name: str
    ) -> Dict[str, Any]:
        """
        Send request and wait for response with timeout.

        Args:
            message: Request message dict (request_id will be added if missing)
            timeout: Response timeout in seconds
            operation_name: Human-readable operation name for logging/errors

        Returns:
            Response dictionary from server

        Raises:
            TimeoutError: If response not received within timeout
        """
        request_id = message.get("request_id") or str(uuid4())
        message["request_id"] = request_id

        future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future

        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"{operation_name} sent: {request_id}")

            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"{operation_name} timed out after {timeout}s")

    def _calculate_websocket_timeout_ms(self, timeout_ms: int, run_in_background: bool) -> int:
        """
        Calculate WebSocket communication timeout based on command execution timeout.

        This is infrastructure overhead (network, serialization, system load),
        not controlled by LLM. The timeout ensures:
        1. Command has time to complete
        2. Result can be transmitted back
        3. System has buffer for GC pauses, network latency, etc.

        Args:
            timeout_ms: Command execution timeout in milliseconds
            run_in_background: Whether command runs in background

        Returns:
            WebSocket communication timeout in milliseconds

        Examples:
            >>> _calculate_websocket_timeout_ms(3000, False)    # 3s command
            13000  # 3s + 10s buffer

            >>> _calculate_websocket_timeout_ms(60000, False)   # 60s command
            72000  # 60s + 12s buffer (20% of 60s)

            >>> _calculate_websocket_timeout_ms(60000, True)    # Background
            10000  # Quick response with task_id
        """
        if run_in_background:
            # Background mode: only waiting for task_id (quick response)
            return 10000  # 10 seconds

        else:
            # Foreground mode: wait for command completion + result transmission buffer
            # Dynamic buffer calculation:
            # - Small commands (<10s): 10s fixed buffer (covers network + serialization)
            # - Large commands (≥10s): 20% proportional buffer (scales with command time)
            #
            # Rationale:
            # - Network latency: ~100ms (localhost)
            # - JSON serialization: 1-2s (large results)
            # - WebSocket overhead: ~100ms
            # - Python GC pauses: ~500ms
            # - System load margin: remaining buffer
            if timeout_ms < 10000:
                buffer_ms = 10000  # 10 seconds
            else:
                buffer_ms = max(10000, int(timeout_ms * 0.2))

            # Infrastructure limit: max 10 minutes WebSocket timeout
            MAX_WEBSOCKET_TIMEOUT_MS = 600000  # 10 minutes
            return min(timeout_ms + buffer_ms, MAX_WEBSOCKET_TIMEOUT_MS)

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to PFC server.

        Returns:
            bool: True if connection successful, False otherwise
        """
        async with self._lock:
            # Clean up any stale pending requests from previous connection
            # This ensures a fresh start and prevents "Future exception was never retrieved" errors
            if self.pending_requests:
                logger.debug(
                    f"Cleaning up {len(self.pending_requests)} pending requests "
                    "from previous connection"
                )
                for future in self.pending_requests.values():
                    if not future.done():
                        try:
                            future.set_exception(ConnectionError("Connection reset"))
                        except Exception:
                            pass  # Future may already be in invalid state
                self.pending_requests.clear()

            # Already connected with valid websocket
            if self.connected and self._websocket:
                try:
                    # Verify websocket is still open
                    if not self._websocket.closed:
                        return True
                except Exception:
                    pass  # Fall through to reconnect

            try:
                self._websocket = await websockets.connect(
                    self.url,
                    ping_interval=30,
                    ping_timeout=50,
                    open_timeout=30,  # Increased from default 10s for slow servers
                    compression=None  # Disable compression for Python 3.6 server compatibility
                )
                self.connected = True
                self._reconnect_count = 0  # Reset reconnect counter on success
                logger.info(f"✓ Connected to PFC server: {self.url}")

                # Start message handler task
                if self._message_task:
                    self._message_task.cancel()
                    try:
                        await self._message_task
                    except asyncio.CancelledError:
                        pass  # Expected cancellation
                self._message_task = asyncio.create_task(self._handle_messages())

                return True

            except Exception as e:
                logger.error(f"Failed to connect to PFC server: {e}")
                self.connected = False
                return False

    async def disconnect(self):
        """Close WebSocket connection and stop auto-reconnect."""
        self._should_stop = True  # Signal to stop reconnection attempts

        async with self._lock:
            # Cancel reconnect task
            if self._reconnect_task:
                self._reconnect_task.cancel()
                try:
                    await self._reconnect_task
                except asyncio.CancelledError:
                    pass  # Expected cancellation
                self._reconnect_task = None

            # Cancel message handler
            if self._message_task:
                self._message_task.cancel()
                try:
                    await self._message_task
                except asyncio.CancelledError:
                    pass  # Expected cancellation
                self._message_task = None

            # Close websocket
            if self._websocket:
                try:
                    await self._websocket.close()
                except Exception:
                    pass  # Already closed or error during close

            self.connected = False
            self._websocket = None
            self._reconnecting = False

            # Cancel all pending requests
            for future in self.pending_requests.values():
                if not future.done():
                    future.set_exception(ConnectionError("Connection closed"))
            self.pending_requests.clear()

            logger.info("✓ Disconnected from PFC server")

    async def _auto_reconnect(self):
        """
        Automatic reconnection task.

        Attempts to reconnect to PFC server after connection loss.
        Respects reconnect_interval and max_reconnect_attempts settings.
        """
        self._reconnecting = True
        self._reconnect_count = 0

        try:
            while not self._should_stop:
                # Check if we've exceeded max attempts (if limit is set)
                if self.max_reconnect_attempts > 0 and self._reconnect_count >= self.max_reconnect_attempts:
                    logger.error(
                        f"Max reconnection attempts ({self.max_reconnect_attempts}) reached. "
                        "Stopping auto-reconnect."
                    )
                    break

                self._reconnect_count += 1
                logger.info(
                    f"Attempting to reconnect to PFC server "
                    f"(attempt {self._reconnect_count}{'/' + str(self.max_reconnect_attempts) if self.max_reconnect_attempts > 0 else ''})"
                )

                # Attempt reconnection
                success = await self.connect()

                if success:
                    logger.info("✓ Successfully reconnected to PFC server")
                    self._reconnecting = False
                    return

                # Wait before next attempt
                logger.debug(f"Waiting {self.reconnect_interval}s before next reconnect attempt")
                await asyncio.sleep(self.reconnect_interval)

        except asyncio.CancelledError:
            logger.debug("Auto-reconnect task cancelled")
        except Exception as e:
            logger.error(f"Error in auto-reconnect task: {e}")
        finally:
            self._reconnecting = False

    async def _handle_messages(self):
        """Handle incoming messages from PFC server."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "result" or msg_type == "quick_python_result":
                        # Request result received (including quick_python_result)
                        request_id = data.get("request_id")
                        if request_id in self.pending_requests:
                            future = self.pending_requests.pop(request_id)
                            if not future.done():
                                future.set_result(data)

                    elif msg_type == "event":
                        # Event from PFC server
                        logger.info(f"Event received: {data.get('event_type')}")
                        # Could trigger callbacks here in the future

                    elif msg_type == "pong":
                        # Ping response
                        logger.debug("Pong received from PFC server")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

        except (ConnectionClosed, ConnectionClosedError) as e:
            logger.warning(f"Connection closed: {e}")
            self.connected = False

            # Cancel all pending requests
            for future in list(self.pending_requests.values()):
                if not future.done():
                    future.set_exception(ConnectionError("Connection lost"))
            self.pending_requests.clear()

            # Trigger auto-reconnect if enabled and not manually disconnected
            if self.auto_reconnect and not self._should_stop:
                logger.info("Connection lost, starting auto-reconnect...")
                if not self._reconnecting and (not self._reconnect_task or self._reconnect_task.done()):
                    self._reconnect_task = asyncio.create_task(self._auto_reconnect())

        except asyncio.CancelledError:
            logger.debug("Message handler cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in message handler: {e}")
            self.connected = False

            # Trigger auto-reconnect for unexpected errors too
            if self.auto_reconnect and not self._should_stop:
                logger.info("Unexpected error, starting auto-reconnect...")
                if not self._reconnecting and (not self._reconnect_task or self._reconnect_task.done()):
                    self._reconnect_task = asyncio.create_task(self._auto_reconnect())

    async def execute_task(
        self,
        script_path: str,
        description: str,
        timeout_ms: Optional[int] = None,
        run_in_background: bool = True,
        session_id: str = "default",
        source: str = "agent",
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Send script file path to PFC server for execution.

        WebSocket communication timeout is automatically calculated based on timeout_ms
        and run_in_background. For None timeout (no limit), uses 10s WebSocket timeout
        in background mode for task_id response.

        Args:
            script_path: Absolute path to Python script file
                Example: "/path/to/pfc_project/scripts/analyze_balls.py"
            description: Human-readable task description explaining what this script does
                Example: "Phase 2: Settling simulation with 50k particles"
            timeout_ms: Script execution timeout in milliseconds (default: None - no timeout)
                Passed to executor for script execution timeout control.
                WebSocket timeout auto-calculated when run_in_background=False.
            run_in_background: Background execution control (default: True - asynchronous)
                Passed to executor to control execution mode.
                Affects WebSocket timeout calculation.
            session_id: Session identifier for task isolation (default: "default")
                Used to separate tasks across different client sessions.
            source: Task source identifier (default: "agent")
                - "agent": Script created/executed by LLM agent
                - "user_console": Script from user Python console
                - "diagnostic": Diagnostic tool operation (e.g., plot capture)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary from PFC server with structure:
                - type: "result" - Message type identifier
                - request_id: str - Unique request identifier
                - status: Literal["success", "error"] - Operation outcome
                - message: str - User-friendly message with result
                - data: Any - Script execution result

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If script execution or WebSocket communication times out

        Note:
            - Server reads and executes the script file locally
            - LLM should read script content first using Read tool
            - Scripts have access to itasca module
            - WebSocket timeout is infrastructure detail, automatically managed
        """
        # Auto-calculate WebSocket timeout (infrastructure detail)
        # For scripts with timeout_ms=None (no script timeout), use background mode logic
        if timeout_ms is None:
            # No script timeout limit, use quick WebSocket timeout for task_id
            websocket_timeout_s = 10.0 if run_in_background else 600.0  # 10s or max 10 min
        else:
            websocket_timeout_s = self._calculate_websocket_timeout_ms(timeout_ms, run_in_background) / 1000.0

        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                return await self._send_request(
                    message={
                        "type": "pfc_task",
                        "session_id": session_id,
                        "script_path": script_path,
                        "description": description,
                        "timeout_ms": timeout_ms,
                        "run_in_background": run_in_background,
                        "source": source
                    },
                    timeout=websocket_timeout_s,
                    operation_name=f"Task execution ({script_path})"
                )

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise ConnectionError(
                        "Failed to execute script after retries. "
                        "Please ensure PFC server is running."
                    ) from e

        raise RuntimeError("Unexpected code path in execute_task")

    async def check_task_status(
        self,
        task_id: str,
        timeout: float = 10.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Check status of a long-running task.

        Args:
            task_id: Task ID returned by long-running command submission
            timeout: Query timeout in seconds (default: 10.0)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary with task status and data

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If status query times out
        """
        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                return await self._send_request(
                    message={"type": "check_task_status", "task_id": task_id},
                    timeout=timeout,
                    operation_name="Task status query"
                )

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise ConnectionError(
                        "Failed to query task status after retries. "
                        "Please ensure PFC server is running."
                    ) from e

        raise RuntimeError("Unexpected code path in check_task_status")

    async def list_tasks(
        self,
        session_id: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None,
        timeout: float = 10.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        List all tracked long-running tasks with pagination support.

        Args:
            session_id: Optional session ID to filter tasks (None = all sessions)
            offset: Skip N most recent tasks (0 = most recent, default: 0)
            limit: Maximum tasks to return (None = all tasks, default: None)
            timeout: Query timeout in seconds (default: 10.0)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary with task list and pagination metadata

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If list query times out
        """
        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                return await self._send_request(
                    message={
                        "type": "list_tasks",
                        "session_id": session_id,
                        "offset": offset,
                        "limit": limit
                    },
                    timeout=timeout,
                    operation_name="List tasks query"
                )

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise ConnectionError(
                        "Failed to list tasks after retries. "
                        "Please ensure PFC server is running."
                    ) from e

        raise RuntimeError("Unexpected code path in list_tasks")

    async def mark_task_notified(
        self,
        task_id: str,
        timeout: float = 5.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Mark a task as notified (completion notification sent to LLM).

        This prevents repeated completion notifications for the same task.

        Args:
            task_id: Task ID to mark as notified
            timeout: Query timeout in seconds (default: 5.0)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary with status

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If request times out
        """
        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                return await self._send_request(
                    message={"type": "mark_task_notified", "task_id": task_id},
                    timeout=timeout,
                    operation_name="Mark task notified"
                )

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise ConnectionError(
                        "Failed to mark task notified after retries. "
                        "Please ensure PFC server is running."
                    ) from e

        raise RuntimeError("Unexpected code path in mark_task_notified")

    async def interrupt_task(
        self,
        task_id: str,
        timeout: float = 5.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Request interrupt for a running PFC task.

        The task will be interrupted at the end of the current cycle.
        Use check_task_status to verify the task was interrupted.

        Args:
            task_id: Task ID to interrupt
            timeout: Request timeout in seconds (default: 5.0)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary with status

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If interrupt request times out
        """
        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                result = await self._send_request(
                    message={"type": "interrupt_task", "task_id": task_id},
                    timeout=timeout,
                    operation_name="Interrupt request"
                )
                logger.info(f"Interrupt request sent for task: {task_id}")
                return result

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise ConnectionError(
                        "Failed to send interrupt request after retries. "
                        "Please ensure PFC server is running."
                    ) from e

        raise RuntimeError("Unexpected code path in interrupt_task")

    async def get_working_directory(
        self,
        timeout: float = 10.0,
        max_retries: int = 2
    ) -> Optional[str]:
        """
        Get PFC server's current working directory.

        Args:
            timeout: Query timeout in seconds (default: 10.0)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            str: PFC's current working directory path, or None if query fails
        """
        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                result = await self._send_request(
                    message={"type": "get_working_directory"},
                    timeout=timeout,
                    operation_name="Working directory query"
                )

                # Extract working directory from result
                if result.get("status") == "success" and result.get("data"):
                    working_dir = result["data"].get("working_directory")
                    logger.info(f"✓ PFC working directory: {working_dir}")
                    return working_dir
                else:
                    logger.warning(f"Failed to get working directory: {result.get('message')}")
                    return None

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    logger.warning(
                        "Failed to query working directory after retries. "
                        "Will use fallback workspace."
                    )
                    return None

            except Exception as e:
                logger.error(f"Working directory query failed: {e}")
                return None

        return None

    async def send_quick_python(
        self,
        code: str,
        workspace_path: str,
        session_id: str = "default",
        timeout_ms: int = 30000,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Send quick Python code from user console for execution.

        Args:
            code: Python code to execute (single or multi-line)
            workspace_path: Absolute path to PFC workspace directory
            session_id: Session identifier for task isolation (default: "default")
            timeout_ms: Execution timeout in milliseconds (default: 30000 = 30s)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary with execution details

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If execution times out
        """
        # Calculate WebSocket timeout (execution timeout + buffer)
        websocket_timeout_ms = self._calculate_websocket_timeout_ms(timeout_ms, run_in_background=False)

        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                return await self._send_request(
                    message={
                        "type": "quick_python",
                        "session_id": session_id,
                        "workspace_path": workspace_path,
                        "code": code,
                        "timeout_ms": timeout_ms
                    },
                    timeout=websocket_timeout_ms / 1000.0,
                    operation_name="Quick Python execution"
                )

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise ConnectionError(
                        "Failed to execute quick Python after retries. "
                        "Please ensure PFC server is running."
                    ) from e

        raise RuntimeError("Unexpected code path in send_quick_python")

    async def ping(self) -> bool:
        """
        Send ping to check server connectivity.

        Returns:
            bool: True if server responds, False otherwise
        """
        if not self.connected:
            return False

        try:
            await self.websocket.send(json.dumps({
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }))
            return True
        except Exception as e:
            logger.error(f"Ping failed: {e}")
            return False

    async def reset_workspace(
        self,
        workspace_path: str,
        timeout: float = 30.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Reset workspace state for testing (clears all history).

        WARNING: This permanently deletes:
        - Quick console scripts and counter
        - All task history (memory + disk)
        - Git pfc-executions branch (all execution snapshots)

        Use only for development/testing to get a clean slate.

        Args:
            workspace_path: Absolute path to PFC workspace directory
            timeout: Request timeout in seconds (default: 30.0)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary with reset details for each component:
                - quick_console: Reset status and deleted script count
                - tasks: Clear status and cleared task count
                - git: Branch reset status and deleted commit count

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If reset request times out
        """
        for attempt in range(max_retries):
            try:
                await self._ensure_connected()
                result = await self._send_request(
                    message={
                        "type": "reset_workspace",
                        "workspace_path": workspace_path
                    },
                    timeout=timeout,
                    operation_name="Workspace reset"
                )
                logger.info(f"✓ Workspace reset completed for: {workspace_path}")
                return result

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    raise ConnectionError(
                        "Failed to reset workspace after retries. "
                        "Please ensure PFC server is running."
                    ) from e

        raise RuntimeError("Unexpected code path in reset_workspace")


# Global client instance (singleton pattern with lazy loading)
_client_instance: Optional[PFCWebSocketClient] = None
_client_lock = asyncio.Lock()


async def get_client() -> PFCWebSocketClient:
    """
    Get or create global PFC WebSocket client instance (lazy loading).

    This function uses lazy loading - the client is created and connected
    only when first needed. Subsequent calls reuse the same instance.

    Returns:
        PFCWebSocketClient: Global client instance

    Raises:
        ConnectionError: If connection to PFC server fails

    Example:
        >>> client = await get_client()
        >>> result = await client.execute_task("/path/to/script.py", "Test script")
    """
    global _client_instance

    async with _client_lock:
        if _client_instance is None:
            _client_instance = PFCWebSocketClient()
            logger.info("Created PFC WebSocket client instance")

        # Auto-connect if not connected (lazy connection)
        if not _client_instance.connected:
            success = await _client_instance.connect()
            if not success:
                raise ConnectionError(
                    "Failed to connect to PFC server. "
                    "Please ensure PFC server is running in PFC GUI."
                )

    return _client_instance


async def close_client():
    """Close global client instance (cleanup)."""
    global _client_instance

    async with _client_lock:
        if _client_instance:
            await _client_instance.disconnect()
            _client_instance = None
            logger.info("Closed PFC WebSocket client")
