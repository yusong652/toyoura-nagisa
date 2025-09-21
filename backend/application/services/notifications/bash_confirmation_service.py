"""
Bash Command Confirmation Service - DDD Application Layer

This service handles bash command confirmation requests, coordinating between
MCP tools that need user approval and the WebSocket frontend for user interaction.

DDD Role: Application Service
- Manages confirmation request lifecycle with timeouts
- Coordinates between MCP tools and WebSocket presentation layer
- Provides async interface for tools to request and await confirmations
"""
import asyncio
import logging
from typing import Optional, Dict
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import create_bash_confirmation_request

logger = logging.getLogger(__name__)




class BashConfirmationService:
    """
    Application Service for Bash Command Confirmations.

    Manages the lifecycle of bash command confirmation requests:
    - Sends confirmation requests to frontend via WebSocket
    - Tracks pending confirmations with timeout handling
    - Provides async interface for MCP tools to await user approval
    - Handles confirmation responses from frontend
    """

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize bash confirmation service.

        Args:
            connection_manager: WebSocket connection manager instance
        """
        self.connection_manager = connection_manager
        self.active_confirmations: Dict[str, asyncio.Future[tuple[bool, Optional[str]]]] = {}  # session_id -> Future

    async def request_confirmation(
        self,
        session_id: str,
        command: str,
        description: Optional[str] = None,
        timeout_seconds: int = 60
    ) -> tuple[bool, Optional[str]]:
        """
        Request user confirmation for a bash command.

        Sends confirmation request to frontend and waits for response.

        Args:
            session_id: WebSocket session ID for the user
            command: The bash command to execute
            description: Optional description of what the command does
            timeout_seconds: Timeout for waiting for confirmation (default 60s)

        Returns:
            tuple[bool, Optional[str]]: (approved, user_message) - approved is True if approved,
                                        False if rejected or timed out. user_message contains
                                        optional message from user when rejecting
        """

        # Create Future for this session's confirmation
        confirmation_future: asyncio.Future[tuple[bool, Optional[str]]] = asyncio.Future()
        self.active_confirmations[session_id] = confirmation_future

        try:
            # Send confirmation request to frontend
            request_msg = create_bash_confirmation_request(
                confirmation_id=session_id,  # Use session_id as confirmation_id
                command=command,
                description=description,
                session_id=session_id
            )

            # Check if session is connected
            if await self.connection_manager.is_connected(session_id):
                await self.connection_manager.send_json(session_id, request_msg)
                logger.info(f"Sent bash confirmation request for session {session_id}, command: {command}")
            else:
                logger.warning(f"Session {session_id} not connected, auto-rejecting bash command")
                return (False, None)

            # Wait for response with timeout
            try:
                approved, user_message = await asyncio.wait_for(
                    confirmation_future,
                    timeout=timeout_seconds
                )
                logger.info(f"Session {session_id} confirmation result: {'approved' if approved else 'rejected'}")
                if user_message:
                    logger.info(f"User message: {user_message}")
                return (approved, user_message)
            except asyncio.TimeoutError:
                logger.warning(f"Session {session_id} confirmation timed out after {timeout_seconds}s")
                return (False, None)

        finally:
            # Clean up the Future
            if session_id in self.active_confirmations:
                del self.active_confirmations[session_id]

    def handle_confirmation_response(self, session_id: str, approved: bool, user_message: Optional[str] = None) -> bool:
        """
        Handle confirmation response from frontend.

        Called by the WebSocket message handler when a BASH_CONFIRMATION_RESPONSE is received.

        Args:
            session_id: The session ID from the response
            approved: Whether the command was approved
            user_message: Optional message from user when rejecting

        Returns:
            bool: True if confirmation was found and processed, False otherwise
        """

        confirmation_future = self.active_confirmations.get(session_id)

        if confirmation_future is None:
            logger.warning(f"Received response for unknown session: {session_id}")
            return False

        if confirmation_future.done():
            logger.warning(f"Received duplicate response for session: {session_id}")
            return False

        # Set the result to wake up the waiting coroutine
        confirmation_future.set_result((approved, user_message))
        logger.info(f"Processed confirmation for session {session_id}: {'approved' if approved else 'rejected'}")
        if user_message:
            logger.info(f"With user message: {user_message}")
        return True

    async def cleanup(self):
        """Clean up service resources."""
        # Reject all active confirmations
        for confirmation_future in self.active_confirmations.values():
            if not confirmation_future.done():
                confirmation_future.set_result((False, None))

        self.active_confirmations.clear()

def get_bash_confirmation_service() -> Optional[BashConfirmationService]:
    """
    Get bash confirmation service from WebSocketHandler.

    Returns:
        BashConfirmationService instance or None if not initialized

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
        if not hasattr(handler, 'bash_confirmation_service'):
            logger.warning("Bash confirmation service not found in WebSocket handler")
            return None

        return handler.bash_confirmation_service

    except Exception as e:
        logger.warning(f"Could not get bash confirmation service: {e}")
        return None