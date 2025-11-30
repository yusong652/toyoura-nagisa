"""
PFC WebSocket Server - Lightweight server to run in PFC GUI IPython shell.

This module provides WebSocket server components for remote PFC control.
Server startup should be done via start_server.py script.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol #type: ignore

from .script_executor import PFCScriptExecutor
from .main_thread_executor import MainThreadExecutor
from .task_manager import TaskManager

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCWebSocketServer:
    """WebSocket server for PFC script execution via main thread queue.

    Script-only workflow: All PFC operations must be executed through Python
    scripts using itasca.command(). Direct command execution is no longer supported.
    """

    def __init__(
        self,
        main_executor,  # type: MainThreadExecutor
        host="localhost",  # type: str
        port=9001,  # type: int
        ping_interval=120,  # type: int
        ping_timeout=300  # type: int
    ):
        # type: (...) -> None
        """
        Initialize WebSocket server.

        Args:
            main_executor: Main thread executor for queue-based command execution
            host: Server host address (default: "localhost")
            port: Server port number (default: 9001)
            ping_interval: Interval between ping frames in seconds (default: 120)
                Note: Longer interval (2 min) to accommodate long-running commands
            ping_timeout: Timeout for pong response in seconds (default: 300)
                Note: Longer timeout (5 min) to prevent disconnection during long tasks
        """
        self.main_executor = main_executor
        self.host = host
        self.port = port
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.task_manager = TaskManager()
        self.script_executor = PFCScriptExecutor(main_executor, self.task_manager)
        self.active_connections = set()
        self.server = None

    @staticmethod
    def _truncate_message(message: str, max_length: int = 5000) -> str:
        """
        Truncate message if too long to prevent WebSocket/JSON size issues.

        Args:
            message: Original message string
            max_length: Maximum message length (default: 5000 characters)

        Returns:
            Truncated message with indicator if truncation occurred
        """
        if len(message) <= max_length:
            return message
        return message[:max_length] + f"\n... (truncated from {len(message)} chars)"

    async def handle_client(self, websocket: WebSocketServerProtocol, path: Optional[str] = None):
        """
        Handle WebSocket client connection.

        Args:
            websocket: WebSocket connection instance
            path: Request path (for websockets 9.x compatibility)
        """
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.active_connections.add(websocket)

        try:
            async for message in websocket:
                try:
                    # Parse incoming message
                    data = json.loads(message)

                    msg_type = data.get("type", "script")

                    if msg_type == "script":
                        # Execute Python script from file path
                        request_id = data.get("request_id", "unknown")
                        session_id = data.get("session_id", "default")  # Session ID for task isolation
                        script_path = data.get("script_path", "")
                        description = data.get("description", "")  # Agent-provided task description
                        timeout_ms = data.get("timeout_ms", None)  # Default None (no timeout)
                        run_in_background = data.get("run_in_background", True)  # Default asynchronous

                        result = await self.script_executor.execute_script(session_id, script_path, description, timeout_ms, run_in_background)

                        # Truncate message before sending (prevent oversized JSON)
                        if "message" in result:
                            result["message"] = self._truncate_message(result["message"])

                        # Send result back
                        response = {
                            "type": "result",
                            "request_id": request_id,
                            **result
                        }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "check_task_status":
                        # Check long-running task status (not a PFC command, uses task manager directly)
                        request_id = data.get("request_id", "unknown")
                        task_id = data.get("task_id", "")

                        result = self.task_manager.get_task_status(task_id)

                        # Truncate message before sending
                        if "message" in result:
                            result["message"] = self._truncate_message(result["message"])

                        # Send result back
                        response = {
                            "type": "result",
                            "request_id": request_id,
                            **result
                        }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "list_tasks":
                        # List all tracked long-running tasks (not a PFC command, uses task manager directly)
                        request_id = data.get("request_id", "unknown")
                        session_id = data.get("session_id")  # Optional session filter
                        offset = data.get("offset", 0)  # Skip N most recent tasks
                        limit = data.get("limit")  # Max tasks to return (None = all)

                        result = self.task_manager.list_all_tasks(
                            session_id=session_id,
                            offset=offset,
                            limit=limit
                        )

                        # Send result back
                        response = {
                            "type": "result",
                            "request_id": request_id,
                            **result
                        }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "mark_task_notified":
                        # Mark task as notified (completion notification sent to LLM)
                        request_id = data.get("request_id", "unknown")
                        task_id = data.get("task_id", "")

                        result = self.task_manager.mark_task_notified(task_id)

                        # Send result back
                        response = {
                            "type": "result",
                            "request_id": request_id,
                            **result
                        }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "get_working_directory":
                        # Get PFC's current working directory
                        request_id = data.get("request_id", "unknown")

                        try:
                            import os
                            cwd = os.getcwd()

                            response = {
                                "type": "result",
                                "request_id": request_id,
                                "status": "success",
                                "message": f"PFC working directory: {cwd}",
                                "data": {
                                    "working_directory": cwd
                                }
                            }
                        except Exception as e:
                            response = {
                                "type": "result",
                                "request_id": request_id,
                                "status": "error",
                                "message": f"Failed to get working directory: {e}",
                                "data": None
                            }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "ping":
                        # Respond to ping
                        try:
                            await websocket.send(json.dumps({
                                "type": "pong",
                                "timestamp": datetime.now().isoformat()
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("Cannot send pong, connection closed")
                            break  # Exit message loop

                    else:
                        logger.warning(f"Unknown message type: {msg_type}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    try:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "Invalid JSON format",
                            "error": str(e)
                        }))
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Cannot send error, connection closed")
                        break  # Exit message loop

                except Exception as e:
                    logger.error(f"Message handling error: {e}")
                    try:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "Internal server error",
                            "error": str(e)
                        }))
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Cannot send error, connection closed")
                        break  # Exit message loop

        except websockets.exceptions.ConnectionClosed:
            pass  # Client disconnected normally

        finally:
            self.active_connections.discard(websocket)

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """
        Broadcast event to all connected clients.

        Args:
            event_type: Type of event (e.g., "simulation_progress")
            data: Event data dictionary
        """
        if not self.active_connections:
            return

        message = json.dumps({
            "type": "event",
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })

        # Send to all connected clients
        disconnected = set()
        for websocket in self.active_connections:
            try:
                await websocket.send(message)
            except Exception as e:
                logger.error(f"Failed to send event to client: {e}")
                disconnected.add(websocket)

        # Remove disconnected clients
        self.active_connections -= disconnected

    async def start(self):
        """Start the WebSocket server (non-blocking)."""

        try:
            # Use websockets 9.1 compatible syntax (Python 3.6)
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout
            )

            # Note: Server is now running in the background
            # websockets.serve() automatically handles connections via the event loop
            # No need to block here - the server will continue running as long as
            # the event loop is active

        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

    async def wait_closed(self):
        """Wait for server to close (for graceful shutdown)."""
        if self.server:
            await self.server.wait_closed()


# Module-level utility function for creating server instances
def create_server(
    main_executor,  # type: MainThreadExecutor
    host="localhost",  # type: str
    port=9001,  # type: int
    ping_interval=120,  # type: int
    ping_timeout=300  # type: int
):
    # type: (...) -> PFCWebSocketServer
    """
    Create a PFC WebSocket server instance.

    Args:
        main_executor: Main thread executor for queue-based command execution
        host: Server host address (default: "localhost")
        port: Server port number (default: 9001)
        ping_interval: Interval between ping frames in seconds (default: 120)
            Note: Longer interval (2 min) to accommodate long-running commands
        ping_timeout: Timeout for pong response in seconds (default: 300)
            Note: Longer timeout (5 min) to prevent disconnection during long tasks

    Returns:
        PFCWebSocketServer: Server instance ready to be started

    Example:
        >>> from pfc_server.main_thread_executor import MainThreadExecutor
        >>> from pfc_server.server import create_server
        >>> executor = MainThreadExecutor()
        >>> server = create_server(executor, host="localhost", port=9001)
        >>> # Use with startup script
    """
    return PFCWebSocketServer(main_executor, host, port, ping_interval, ping_timeout)
