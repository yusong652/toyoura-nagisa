"""
PFC WebSocket Server - Lightweight server to run in PFC GUI IPython shell.

Usage in PFC GUI IPython shell:
    >>> import itasca  # PFC SDK
    >>> from pfc_server import server
    >>> server.start()  # Starts WebSocket server on port 9001
"""

import asyncio
import json
import logging
from datetime import datetime

# Python 3.6 compatible typing
try:
    from typing import Any, Dict, Optional
except ImportError:
    # Fallback for older typing versions
    Any = None
    Dict = dict
    Optional = None

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    print("ERROR: websockets package not found!")
    print("Please install: pip install websockets")
    raise

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PFC-Server")

# Global reference to itasca module (imported in PFC GUI)
itasca = None


class PFCCommandExecutor:
    """Execute PFC commands using itasca SDK."""

    def __init__(self):
        """Initialize executor with itasca module reference."""
        global itasca
        try:
            import itasca as _itasca
            itasca = _itasca
            self.itasca = itasca
            logger.info("✓ ITASCA SDK loaded successfully")
        except ImportError:
            logger.warning("⚠ ITASCA SDK not available (running outside PFC GUI)")
            self.itasca = None

    async def execute_command(
        self,
        command: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a PFC command and return the result.

        Args:
            command: Command in dot notation (e.g., "ball.create", "cycle.run")
            params: Command parameters dictionary

        Returns:
            Result dictionary with structure:
                - status: "success" or "error"
                - data: Command result data
                - message: Human-readable message
                - error: Error details if status="error"
        """
        try:
            if not self.itasca:
                return {
                    "status": "error",
                    "message": "ITASCA SDK not available",
                    "error": "Server not running in PFC GUI environment"
                }

            logger.info(f"Executing command: {command} with params: {params}")

            # Special case: "command" executes a PFC command string
            if command == "command" and "cmd" in params:
                cmd_str = params["cmd"]
                logger.info(f"Executing PFC command string: {cmd_str}")
                result = self.itasca.command(cmd_str)
                return {
                    "status": "success",
                    "data": self._serialize_result(result),
                    "message": f"PFC command executed: {cmd_str}"
                }

            # Parse command path (e.g., "ball.create" -> itasca.ball.create)
            parts = command.split('.')
            obj = self.itasca

            for part in parts[:-1]:
                obj = getattr(obj, part)

            # Execute the command
            func = getattr(obj, parts[-1])

            # Call function with parameters
            if callable(func):
                result = func(**params)
            else:
                result = func

            return {
                "status": "success",
                "data": self._serialize_result(result),
                "message": f"Command '{command}' executed successfully"
            }

        except AttributeError as e:
            logger.error(f"Command not found: {command} - {e}")
            return {
                "status": "error",
                "message": f"Command '{command}' not found in ITASCA SDK",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "status": "error",
                "message": f"Command execution failed",
                "error": str(e)
            }

    def _serialize_result(self, result: Any) -> Any:
        """Convert PFC objects to JSON-serializable format."""
        if result is None:
            return None
        elif isinstance(result, (str, int, float, bool)):
            return result
        elif isinstance(result, (list, tuple)):
            return [self._serialize_result(item) for item in result]
        elif isinstance(result, dict):
            return {k: self._serialize_result(v) for k, v in result.items()}
        else:
            # For complex PFC objects, return string representation
            return str(result)


class PFCWebSocketServer:
    """WebSocket server for PFC command execution."""

    def __init__(self, host: str = "localhost", port: int = 9001):
        """
        Initialize WebSocket server.

        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host
        self.port = port
        self.executor = PFCCommandExecutor()
        self.active_connections = set()
        self.server = None

    async def handle_client(self, websocket: WebSocketServerProtocol, path: str = None):
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
                        params = data.get("params", {})

                        result = await self.executor.execute_command(command, params)

                        # Send result back
                        response = {
                            "type": "result",
                            "command_id": command_id,
                            **result
                        }

                        await websocket.send(json.dumps(response))
                        logger.info(f"✓ Command result sent: {command_id}")

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
        logger.info(f"🚀 Starting PFC WebSocket Server on {self.host}:{self.port}")

        try:
            async with websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10
            ):
                logger.info(f"✓ Server running on ws://{self.host}:{self.port}")
                logger.info("Press Ctrl+C to stop the server")

                # Keep server running
                await asyncio.Future()  # Run forever

        except Exception as e:
            logger.error(f"Server error: {e}")
            raise


# Global server instance
_server_instance: Optional[PFCWebSocketServer] = None


def start(host: str = "localhost", port: int = 9001):
    """
    Start PFC WebSocket server (blocking call).

    Usage in PFC GUI IPython shell:
        >>> from pfc_server import server
        >>> server.start()

    Args:
        host: Server host address (default: localhost)
        port: Server port number (default: 9001)
    """
    global _server_instance

    _server_instance = PFCWebSocketServer(host, port)

    try:
        # Python 3.6 compatible event loop execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_server_instance.start())
    except KeyboardInterrupt:
        logger.info("\n✓ Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        raise
    finally:
        loop.close()


def start_background(host: str = "localhost", port: int = 9001):
    """
    Start PFC WebSocket server in background (non-blocking).

    Usage in PFC GUI IPython shell:
        >>> from pfc_server import server
        >>> server.start_background()
        >>> # Continue using PFC GUI while server runs

    Args:
        host: Server host address (default: localhost)
        port: Server port number (default: 9001)

    Returns:
        asyncio.Task: Server task (can be cancelled with task.cancel())
    """
    global _server_instance

    _server_instance = PFCWebSocketServer(host, port)

    # Get or create event loop (Python 3.6 compatible)
    try:
        # Python 3.7+
        loop = asyncio.get_running_loop()
    except AttributeError:
        # Python 3.6 fallback
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # No running loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Start server as background task
    task = loop.create_task(_server_instance.start())
    logger.info("✓ Server started in background")
    return task


def get_server() -> Optional[PFCWebSocketServer]:
    """Get the current server instance."""
    return _server_instance


if __name__ == "__main__":
    # Direct execution (for testing)
    start()
