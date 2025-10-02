"""
PFC WebSocket Client - Connects aiNagisa backend to PFC server.

This client maintains a WebSocket connection to the PFC server running
in the PFC GUI IPython shell, enabling real-time command execution.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4
from datetime import datetime

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    raise ImportError("websockets package required: pip install websockets")

logger = logging.getLogger("PFC-Client")


class PFCWebSocketClient:
    """WebSocket client for communicating with PFC server."""

    def __init__(self, url: str = "ws://localhost:9001"):
        """
        Initialize PFC WebSocket client.

        Args:
            url: WebSocket server URL (default: ws://localhost:9001)
        """
        self.url = url
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.connected = False
        self.pending_commands: Dict[str, asyncio.Future] = {}

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to PFC server.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.websocket = await websockets.connect(
                self.url,
                ping_interval=30,
                ping_timeout=10
            )
            self.connected = True
            logger.info(f"✓ Connected to PFC server: {self.url}")

            # Start message handler
            asyncio.create_task(self._handle_messages())

            return True

        except Exception as e:
            logger.error(f"Failed to connect to PFC server: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Close WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("✓ Disconnected from PFC server")

    async def _handle_messages(self):
        """Handle incoming messages from PFC server."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "result":
                        # Command result received
                        command_id = data.get("command_id")
                        if command_id in self.pending_commands:
                            future = self.pending_commands.pop(command_id)
                            future.set_result(data)

                    elif msg_type == "event":
                        # Event from PFC server
                        logger.info(f"Event received: {data.get('event_type')}")
                        # Could trigger callbacks here in the future

                    elif msg_type == "pong":
                        # Ping response
                        pass

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Connection closed by server")
            self.connected = False

    async def send_command(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Send command to PFC server and wait for result.

        Args:
            command: Command in dot notation (e.g., "ball.create")
            params: Command parameters dictionary
            timeout: Command timeout in seconds (default: 30.0)

        Returns:
            Result dictionary from PFC server with structure:
                - status: "success" or "error"
                - data: Command result data
                - message: Human-readable message
                - error: Error details if status="error"

        Raises:
            ConnectionError: If not connected to PFC server
            TimeoutError: If command execution times out
        """
        if not self.connected:
            raise ConnectionError("Not connected to PFC server")

        command_id = str(uuid4())
        params = params or {}

        # Create command message
        message = {
            "type": "command",
            "command_id": command_id,
            "command": command,
            "params": params
        }

        # Create future for result
        future = asyncio.get_event_loop().create_future()
        self.pending_commands[command_id] = future

        try:
            # Send command
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Command sent: {command_id} - {command}")

            # Wait for result with timeout
            result = await asyncio.wait_for(future, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            self.pending_commands.pop(command_id, None)
            raise TimeoutError(f"Command '{command}' timed out after {timeout}s")

        except Exception as e:
            self.pending_commands.pop(command_id, None)
            logger.error(f"Command execution failed: {e}")
            raise

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


# Global client instance
_client_instance: Optional[PFCWebSocketClient] = None


async def get_client() -> PFCWebSocketClient:
    """
    Get or create global PFC WebSocket client instance.

    Returns:
        PFCWebSocketClient: Global client instance

    Raises:
        ConnectionError: If connection to PFC server fails
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = PFCWebSocketClient()

    if not _client_instance.connected:
        success = await _client_instance.connect()
        if not success:
            raise ConnectionError(
                "Failed to connect to PFC server. "
                "Please ensure PFC server is running in PFC GUI."
            )

    return _client_instance


async def close_client():
    """Close global client instance."""
    global _client_instance

    if _client_instance:
        await _client_instance.disconnect()
        _client_instance = None
