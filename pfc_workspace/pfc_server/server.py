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

from .executor import PFCCommandExecutor
from .script_executor import PFCScriptExecutor

# Module logger
logger = logging.getLogger("PFC-Server")


class PFCWebSocketServer:
    """WebSocket server for PFC command execution."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9001,
        ping_interval: int = 30,
        ping_timeout: int = 10
    ):
        """
        Initialize WebSocket server.

        Args:
            host: Server host address
            port: Server port number
            ping_interval: Interval between ping frames in seconds
            ping_timeout: Timeout for pong response in seconds
        """
        self.host = host
        self.port = port
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.executor = PFCCommandExecutor()
        self.script_executor = PFCScriptExecutor()
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
        logger.info(f"✓ Client connected: {client_id}")
        self.active_connections.add(websocket)

        try:
            async for message in websocket:
                try:
                    # Parse incoming message
                    data = json.loads(message)
                    logger.debug(f"Received message: {data}")

                    msg_type = data.get("type", "command")

                    if msg_type == "command":
                        # Execute command
                        command_id = data.get("command_id", "unknown")
                        command = data.get("command", "")
                        arg = data.get("arg")  # Single positional argument (can be None)
                        params = data.get("params", {})

                        result = await self.executor.execute_command(command, arg, params)

                        # Truncate message before sending (prevent oversized JSON)
                        if "message" in result:
                            result["message"] = self._truncate_message(result["message"])

                        # Send result back
                        response = {
                            "type": "result",
                            "command_id": command_id,
                            **result
                        }

                        await websocket.send(json.dumps(response))
                        logger.info(f"✓ Command result sent: {command_id}")

                    elif msg_type == "script":
                        # Execute Python script from file path
                        command_id = data.get("command_id", "unknown")
                        script_path = data.get("script_path", "")

                        result = await self.script_executor.execute_script(script_path)

                        # Truncate message before sending (prevent oversized JSON)
                        if "message" in result:
                            result["message"] = self._truncate_message(result["message"])

                        # Send result back
                        response = {
                            "type": "result",
                            "command_id": command_id,
                            **result
                        }

                        await websocket.send(json.dumps(response))
                        logger.info(f"✓ Script result sent: {command_id}")

                    elif msg_type == "ping":
                        # Respond to ping
                        await websocket.send(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        }))

                    else:
                        logger.warning(f"Unknown message type: {msg_type}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format",
                        "error": str(e)
                    }))

                except Exception as e:
                    logger.error(f"Message handling error: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Internal server error",
                        "error": str(e)
                    }))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"✗ Client disconnected: {client_id}")

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
        """Start the WebSocket server."""
        logger.info(f"Starting PFC WebSocket Server on {self.host}:{self.port}")

        try:
            async with websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout
            ):
                logger.info(f"✓ Server running on ws://{self.host}:{self.port}")
                # Keep server running forever
                await asyncio.Future()

        except Exception as e:
            logger.error(f"Server error: {e}")
            raise


# Module-level utility function for creating server instances
def create_server(
    host: str = "localhost",
    port: int = 9001,
    ping_interval: int = 30,
    ping_timeout: int = 10
) -> PFCWebSocketServer:
    """
    Create a PFC WebSocket server instance.

    Args:
        host: Server host address (default: localhost)
        port: Server port number (default: 9001)
        ping_interval: Interval between ping frames in seconds (default: 30)
        ping_timeout: Timeout for pong response in seconds (default: 10)

    Returns:
        PFCWebSocketServer: Server instance ready to be started

    Example:
        >>> from pfc_server.server import create_server
        >>> server = create_server(host="localhost", port=9001)
        >>> # Use with startup script to run in background
    """
    return PFCWebSocketServer(host, port, ping_interval, ping_timeout)
