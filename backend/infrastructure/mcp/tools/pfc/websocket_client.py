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

import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

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
        self._websocket: Optional[Any] = None
        self.connected = False
        self.pending_commands: Dict[str, asyncio.Future] = {}
        self._message_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

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

    async def connect(self) -> bool:
        """
        Establish WebSocket connection to PFC server.

        Returns:
            bool: True if connection successful, False otherwise
        """
        async with self._lock:
            # Already connected (idempotent)
            if self.connected and self._websocket:
                return True

            try:
                self._websocket = await websockets.connect(
                    self.url,
                    ping_interval=30,
                    ping_timeout=10
                )
                self.connected = True
                logger.info(f"✓ Connected to PFC server: {self.url}")

                # Start message handler task
                if self._message_task:
                    self._message_task.cancel()
                self._message_task = asyncio.create_task(self._handle_messages())

                return True

            except Exception as e:
                logger.error(f"Failed to connect to PFC server: {e}")
                self.connected = False
                return False

    async def disconnect(self):
        """Close WebSocket connection."""
        async with self._lock:
            # Cancel message handler
            if self._message_task:
                self._message_task.cancel()
                self._message_task = None

            # Close websocket
            if self._websocket:
                try:
                    await self._websocket.close()
                except Exception:
                    pass  # Already closed or error during close

            self.connected = False
            self._websocket = None

            # Cancel all pending commands
            for future in self.pending_commands.values():
                if not future.done():
                    future.set_exception(ConnectionError("Connection closed"))
            self.pending_commands.clear()

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
            # Cancel all pending commands
            for future in list(self.pending_commands.values()):
                if not future.done():
                    future.set_exception(ConnectionError("Connection lost"))
            self.pending_commands.clear()
        except asyncio.CancelledError:
            logger.debug("Message handler cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in message handler: {e}")
            self.connected = False

    async def send_command(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Send command to PFC server and wait for result.

        Args:
            command: Command in dot notation (e.g., "ball.create")
            params: Command parameters dictionary
            timeout: Command timeout in seconds (default: 30.0)
            max_retries: Maximum retry attempts on connection failure (default: 2)

        Returns:
            Result dictionary from PFC server with structure:
                - status: "success" or "error"
                - data: Command result data
                - message: Human-readable message
                - error: Error details if status="error"

        Raises:
            ConnectionError: If connection to PFC server fails after retries
            TimeoutError: If command execution times out
        """
        for attempt in range(max_retries):
            try:
                # Ensure connected (auto-reconnect if needed)
                if not self.connected:
                    success = await self.connect()
                    if not success:
                        raise ConnectionError("Failed to connect to PFC server")

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

            except (ConnectionClosed, ConnectionClosedError, ConnectionError) as e:
                logger.warning(f"Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                self.connected = False

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)  # Brief delay before retry
                    continue
                else:
                    raise ConnectionError(
                        "Failed to execute command after retries. "
                        "Please ensure PFC server is running."
                    ) from e

            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                raise

        # Fallback: should never reach here due to retry logic
        raise RuntimeError("Unexpected code path in send_command")

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
        >>> result = await client.send_command("ball.count", {})
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
