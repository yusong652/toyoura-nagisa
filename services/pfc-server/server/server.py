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
from .quick_console_manager import QuickConsoleManager
from .interrupt_manager import request_interrupt
from .diagnostic_executor import submit_diagnostic, is_callback_registered

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
        # Quick console managers cache (workspace_path -> QuickConsoleManager)
        self._quick_console_managers = {}  # type: Dict[str, QuickConsoleManager]

    def _get_quick_console_manager(self, workspace_path):
        # type: (str) -> QuickConsoleManager
        """
        Get or create QuickConsoleManager for a workspace.

        Args:
            workspace_path: Absolute path to the PFC workspace directory

        Returns:
            QuickConsoleManager instance for the workspace
        """
        if workspace_path not in self._quick_console_managers:
            self._quick_console_managers[workspace_path] = QuickConsoleManager(workspace_path)
        return self._quick_console_managers[workspace_path]

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

                    msg_type = data.get("type", "pfc_task")

                    if msg_type == "pfc_task":
                        # Execute Python script from file path
                        request_id = data.get("request_id", "unknown")
                        session_id = data.get("session_id", "default")  # Session ID for task isolation
                        script_path = data.get("script_path", "")
                        description = data.get("description", "")  # Agent-provided task description
                        timeout_ms = data.get("timeout_ms", None)  # Default None (no timeout)
                        run_in_background = data.get("run_in_background", True)  # Default asynchronous
                        source = data.get("source", "agent")  # Task source: agent, user_console, diagnostic

                        # Only agent tasks get git snapshots
                        enable_git_snapshot = (source == "agent")

                        result = await self.script_executor.execute_script(
                            session_id, script_path, description, timeout_ms, run_in_background,
                            source=source, enable_git_snapshot=enable_git_snapshot
                        )

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
                        source = data.get("source")  # Optional source filter (agent, user_console, diagnostic)
                        offset = data.get("offset", 0)  # Skip N most recent tasks
                        limit = data.get("limit")  # Max tasks to return (None = all)

                        result = self.task_manager.list_all_tasks(
                            session_id=session_id,
                            source=source,
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

                    elif msg_type == "quick_python":
                        # Execute quick Python code from user console
                        request_id = data.get("request_id", "unknown")
                        session_id = data.get("session_id", "default")
                        workspace_path = data.get("workspace_path", "")
                        code = data.get("code", "")
                        timeout_ms = data.get("timeout_ms", 30000)  # Default 30s for quick commands

                        try:
                            # Validate required parameters
                            if not workspace_path:
                                raise ValueError("workspace_path is required")
                            if not code or not code.strip():
                                raise ValueError("code cannot be empty")

                            # Get or create QuickConsoleManager for this workspace
                            console_manager = self._get_quick_console_manager(workspace_path)

                            # Create temporary script file
                            code_preview = console_manager.get_code_preview(code)
                            script_name, script_path, _ = console_manager.create_script(
                                code,
                                description=code_preview
                            )

                            # Execute using existing script executor (synchronous for quick commands)
                            result = await self.script_executor.execute_script(
                                session_id=session_id,
                                script_path=script_path,
                                description=code_preview,
                                timeout_ms=timeout_ms,
                                run_in_background=False,  # Quick commands are always synchronous
                                source="user_console",
                                enable_git_snapshot=False  # No git snapshot for quick commands
                            )

                            # Add code preview to response data
                            if result.get("data"):
                                result["data"]["code_preview"] = code_preview

                            # Truncate message before sending
                            if "message" in result:
                                result["message"] = self._truncate_message(result["message"])

                            response = {
                                "type": "quick_python_result",
                                "request_id": request_id,
                                **result
                            }

                        except ValueError as e:
                            response = {
                                "type": "quick_python_result",
                                "request_id": request_id,
                                "status": "error",
                                "message": str(e),
                                "data": None
                            }
                        except Exception as e:
                            logger.error(f"Quick Python execution failed: {e}")
                            response = {
                                "type": "quick_python_result",
                                "request_id": request_id,
                                "status": "error",
                                "message": f"Execution failed: {e}",
                                "data": None
                            }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "interrupt_task":
                        # Request interrupt for a running task
                        request_id = data.get("request_id", "unknown")
                        task_id = data.get("task_id", "")

                        if not task_id:
                            response = {
                                "type": "result",
                                "request_id": request_id,
                                "status": "error",
                                "message": "task_id is required",
                                "data": None
                            }
                        else:
                            # Request interrupt (will be checked by PFC callback)
                            success = request_interrupt(task_id)
                            if success:
                                response = {
                                    "type": "result",
                                    "request_id": request_id,
                                    "status": "success",
                                    "message": "Interrupt requested for task: {}".format(task_id),
                                    "data": {"task_id": task_id, "interrupt_requested": True}
                                }
                            else:
                                response = {
                                    "type": "result",
                                    "request_id": request_id,
                                    "status": "error",
                                    "message": "Failed to request interrupt",
                                    "data": None
                                }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "diagnostic_execute":
                        # Execute diagnostic script with smart path selection
                        # Used for quick operations like plot capture that need to run
                        # even when main thread is blocked by cycle() computation
                        #
                        # Execution strategy:
                        # 1. Try queue execution first (1s timeout) - works when idle
                        # 2. If queue blocked, use callback execution - works during cycle
                        request_id = data.get("request_id", "unknown")
                        script_path = data.get("script_path", "")
                        timeout_ms = data.get("timeout_ms", 30000)  # Default 30s

                        try:
                            if not script_path:
                                raise ValueError("script_path is required")

                            import os
                            from io import StringIO
                            import uuid

                            # Read script content
                            with open(script_path, 'r', encoding='utf-8') as f:
                                script_content = f.read()

                            # Generate task_id for tracking
                            task_id = uuid.uuid4().hex[:8]
                            output_buffer = StringIO()

                            # Strategy 1: Try queue execution with short timeout (1 second)
                            # This works when PFC is idle (no cycle running)
                            queue_future = self.main_executor.submit(
                                self.script_executor._execute_script_sync,
                                script_path,
                                script_content,
                                output_buffer,
                                task_id
                            )

                            try:
                                # Wait 1 second for queue execution
                                result = queue_future.result(timeout=1.0)
                                logger.info("Diagnostic executed via queue: {}".format(
                                    os.path.basename(script_path)
                                ))
                                response = {
                                    "type": "diagnostic_result",
                                    "request_id": request_id,
                                    "execution_path": "queue",
                                    **result
                                }

                            except Exception as queue_error:
                                # Queue execution failed or timed out
                                # Strategy 2: Use callback execution (works during cycle)
                                import concurrent.futures

                                # Check if it's a timeout (queue blocked) vs actual error
                                is_timeout = isinstance(queue_error, concurrent.futures.TimeoutError)

                                if is_timeout:
                                    logger.info("Queue blocked, switching to callback execution")

                                    if not is_callback_registered():
                                        raise RuntimeError(
                                            "Diagnostic callback not registered and queue is blocked. "
                                            "Restart PFC server to enable callback execution."
                                        )

                                    # Submit to callback executor
                                    callback_future = submit_diagnostic(script_path)

                                    # Wait for callback execution
                                    timeout_sec = (timeout_ms - 1000) / 1000.0  # Subtract queue timeout
                                    timeout_sec = max(timeout_sec, 1.0)  # At least 1 second

                                    try:
                                        result = callback_future.result(timeout=timeout_sec)
                                        logger.info("Diagnostic executed via callback: {}".format(
                                            os.path.basename(script_path)
                                        ))
                                        response = {
                                            "type": "diagnostic_result",
                                            "request_id": request_id,
                                            "execution_path": "callback",
                                            **result
                                        }
                                    except concurrent.futures.TimeoutError:
                                        response = {
                                            "type": "diagnostic_result",
                                            "request_id": request_id,
                                            "status": "timeout",
                                            "message": "Diagnostic timed out after {}ms. "
                                                       "Queue blocked and no cycle running.".format(timeout_ms),
                                            "data": None
                                        }
                                else:
                                    # Actual execution error (not timeout)
                                    raise queue_error

                        except ValueError as e:
                            response = {
                                "type": "diagnostic_result",
                                "request_id": request_id,
                                "status": "error",
                                "message": str(e),
                                "data": None
                            }
                        except RuntimeError as e:
                            response = {
                                "type": "diagnostic_result",
                                "request_id": request_id,
                                "status": "error",
                                "message": str(e),
                                "data": None
                            }
                        except Exception as e:
                            logger.error(f"Diagnostic execution failed: {e}")
                            response = {
                                "type": "diagnostic_result",
                                "request_id": request_id,
                                "status": "error",
                                "message": f"Diagnostic execution failed: {e}",
                                "data": None
                            }

                        try:
                            await websocket.send(json.dumps(response))
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Cannot send result, connection closed: {request_id}")
                            break  # Exit message loop

                    elif msg_type == "reset_workspace":
                        # Reset workspace state for testing (clears all history)
                        request_id = data.get("request_id", "unknown")
                        workspace_path = data.get("workspace_path", "")

                        try:
                            results = []

                            # 1. Reset quick console (if manager exists for workspace)
                            if workspace_path and workspace_path in self._quick_console_managers:
                                console_result = self._quick_console_managers[workspace_path].reset()
                                results.append(console_result)
                                # Remove from cache after reset
                                del self._quick_console_managers[workspace_path]
                            else:
                                results.append({
                                    "success": True,
                                    "message": "No quick console to reset",
                                    "deleted_scripts": 0
                                })

                            # 2. Clear all task history
                            task_result = self.task_manager.clear_all_tasks()
                            results.append(task_result)

                            # 3. Reset git execution branch
                            from .git_version_manager import get_git_manager
                            if workspace_path:
                                git_manager = get_git_manager(workspace_path)
                                git_result = git_manager.reset_execution_branch()
                                results.append(git_result)
                            else:
                                results.append({
                                    "success": True,
                                    "message": "No workspace path provided, skipping git reset",
                                    "deleted_commits": 0
                                })

                            # Build summary
                            all_success = all(r.get("success", False) for r in results)
                            summary_parts = [r.get("message", "") for r in results]

                            response = {
                                "type": "result",
                                "request_id": request_id,
                                "status": "success" if all_success else "partial",
                                "message": "Workspace reset complete:\n- " + "\n- ".join(summary_parts),
                                "data": {
                                    "quick_console": results[0],
                                    "tasks": results[1],
                                    "git": results[2]
                                }
                            }

                            logger.info("✓ Workspace reset completed for: {}".format(
                                workspace_path or "(no workspace)"
                            ))

                        except Exception as e:
                            logger.error(f"Workspace reset failed: {e}")
                            response = {
                                "type": "result",
                                "request_id": request_id,
                                "status": "error",
                                "message": f"Reset failed: {e}",
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
