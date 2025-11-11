"""
Tool Confirmation Service - DDD Application Layer

This service handles tool confirmation requests (bash, edit, write, etc.), coordinating between
MCP tools that need user approval and the WebSocket frontend for user interaction.

DDD Role: Application Service
- Manages confirmation request lifecycle with timeouts
- Coordinates between MCP tools and WebSocket presentation layer
- Provides async interface for tools to request and await confirmations
"""
import asyncio
import logging
import uuid
from typing import Optional, Dict
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


class ToolConfirmationService:
    """
    Application Service for Tool Confirmations.

    Manages the lifecycle of tool confirmation requests (bash, edit, write, etc.):
    - Sends confirmation requests to frontend via WebSocket
    - Tracks pending confirmations with timeout handling
    - Provides async interface for MCP tools to await user approval
    - Handles confirmation responses from frontend
    """

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize tool confirmation service.

        Args:
            connection_manager: WebSocket connection manager instance
        """
        self.connection_manager = connection_manager
        self.active_confirmations: Dict[str, asyncio.Future[tuple[bool, Optional[str]]]] = {}  # tool_call_id -> Future

    async def request_confirmation(
        self,
        session_id: str,
        message_id: str,
        tool_call_id: str,
        tool_name: str,
        command: str,
        description: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Request user confirmation for a tool execution.

        Sends confirmation request to frontend and waits for response.

        Args:
            session_id: WebSocket session ID for the user
            message_id: ID of the message containing this tool call (for unique identification)
            tool_call_id: ID of the tool call (combined with message_id for matching)
            tool_name: Name of the tool requiring confirmation (bash, edit, write)
            command: The command/operation to execute
            description: Optional description of what the command does
            timeout_seconds: Timeout for waiting for confirmation (default None = infinite wait)

        Returns:
            tuple[bool, Optional[str]]: (approved, user_message) - approved is True if approved,
                                        False if rejected or timed out. user_message contains
                                        optional message from user when rejecting
        """

        # Create Future for this confirmation request (keyed by tool_call_id)
        confirmation_future: asyncio.Future[tuple[bool, Optional[str]]] = asyncio.Future()
        self.active_confirmations[tool_call_id] = confirmation_future

        try:
            # Send confirmation request to frontend (include message_id for unique identification)
            request_msg = create_message(
                MessageType.TOOL_CONFIRMATION_REQUEST,
                message_id=message_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                command=command,
                description=description,
                session_id=session_id
            ).model_dump(mode="json", exclude_none=True)

            # Check if session is connected
            if await self.connection_manager.is_connected(session_id):
                await self.connection_manager.send_json(session_id, request_msg)
                logger.info(f"Sent tool confirmation request {tool_call_id} for session {session_id}, tool: {tool_name}, command: {command}")
            else:
                logger.warning(f"Session {session_id} not connected, auto-rejecting tool: {tool_name}")
                return (False, None)

            # Wait for response (infinite wait if timeout_seconds is None)
            try:
                approved, user_message = await asyncio.wait_for(
                    confirmation_future,
                    timeout=timeout_seconds
                )
                logger.info(f"Tool call {tool_call_id} confirmation result: {'approved' if approved else 'rejected'}")
                if user_message:
                    logger.info(f"User message: {user_message}")
                return (approved, user_message)
            except asyncio.TimeoutError:
                timeout_str = f"{timeout_seconds}s" if timeout_seconds else "unknown"
                logger.warning(f"Tool call {tool_call_id} confirmation timed out after {timeout_str}")
                return (False, None)

        finally:
            # Clean up the Future
            if tool_call_id in self.active_confirmations:
                del self.active_confirmations[tool_call_id]

    def handle_confirmation_response(self, tool_call_id: str, approved: bool, user_message: Optional[str] = None) -> bool:
        """
        Handle confirmation response from frontend.

        Called by the WebSocket message handler when a TOOL_CONFIRMATION_RESPONSE is received.

        Args:
            tool_call_id: The tool call ID from the response
            approved: Whether the command was approved
            user_message: Optional message from user when rejecting

        Returns:
            bool: True if confirmation was found and processed, False otherwise
        """

        confirmation_future = self.active_confirmations.get(tool_call_id)

        if confirmation_future is None:
            logger.warning(f"Received response for unknown tool call: {tool_call_id}")
            return False

        if confirmation_future.done():
            logger.warning(f"Received duplicate response for tool call: {tool_call_id}")
            return False

        # Set the result to wake up the waiting coroutine
        confirmation_future.set_result((approved, user_message))
        logger.info(f"Processed tool call {tool_call_id} confirmation: {'approved' if approved else 'rejected'}")
        if user_message:
            logger.info(f"With user message: {user_message}")
        return True

def get_tool_confirmation_service() -> Optional[ToolConfirmationService]:
    """
    Get tool confirmation service from WebSocketHandler.

    Returns:
        ToolConfirmationService instance or None if not initialized

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
        if not hasattr(handler, 'tool_confirmation_service'):
            logger.warning("Tool confirmation service not found in WebSocket handler")
            return None

        return handler.tool_confirmation_service

    except Exception as e:
        logger.warning(f"Could not get tool confirmation service: {e}")
        return None
