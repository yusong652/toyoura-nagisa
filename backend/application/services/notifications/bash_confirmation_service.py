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
import uuid
from typing import Optional, Dict
from datetime import datetime
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import create_bash_confirmation_request

logger = logging.getLogger(__name__)


class PendingConfirmation:
    """Represents a pending bash command confirmation request."""

    def __init__(self, confirmation_id: str, command: str, description: Optional[str] = None):
        """
        Initialize pending confirmation.

        Args:
            confirmation_id: Unique ID for this confirmation
            command: The bash command to execute
            description: Optional description of what the command does
        """
        self.confirmation_id = confirmation_id
        self.command = command
        self.description = description
        self.created_at = datetime.now()
        self.future: asyncio.Future[tuple[bool, Optional[str]]] = asyncio.Future()  # (approved, user_message)


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
        self.pending_confirmations: Dict[str, PendingConfirmation] = {}

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

        # Generate unique confirmation ID
        confirmation_id = str(uuid.uuid4())

        # Create pending confirmation
        pending = PendingConfirmation(confirmation_id, command, description)
        self.pending_confirmations[confirmation_id] = pending

        try:
            # Send confirmation request to frontend
            request_msg = create_bash_confirmation_request(
                confirmation_id=confirmation_id,
                command=command,
                description=description,
                session_id=session_id
            )

            # Check if session is connected
            if await self.connection_manager.is_connected(session_id):
                await self.connection_manager.send_json(session_id, request_msg)
                logger.info(f"Sent bash confirmation request {confirmation_id} for command: {command}")
            else:
                logger.warning(f"Session {session_id} not connected, auto-rejecting bash command")
                return (False, None)

            # Wait for response with timeout - use non-blocking approach
            start_time = datetime.now()
            check_interval = 0.1  # Check every 100ms

            while True:
                # Check if we have a response
                if pending.future.done():
                    approved, user_message = pending.future.result()
                    logger.info(f"Confirmation {confirmation_id} result: {'approved' if approved else 'rejected'}")
                    if user_message:
                        logger.info(f"User message: {user_message}")
                    # Clean up after successful response
                    if confirmation_id in self.pending_confirmations:
                        del self.pending_confirmations[confirmation_id]
                    return (approved, user_message)

                # Check for timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout_seconds:
                    logger.warning(f"Confirmation {confirmation_id} timed out after {timeout_seconds}s")
                    # Clean up after timeout
                    if confirmation_id in self.pending_confirmations:
                        del self.pending_confirmations[confirmation_id]
                    return (False, None)

                # Sleep briefly to allow other tasks to run
                await asyncio.sleep(check_interval)

        finally:
            pass  # Don't clean up here - only clean up after we get a result or timeout

    def handle_confirmation_response(self, confirmation_id: str, approved: bool, user_message: Optional[str] = None) -> bool:
        """
        Handle confirmation response from frontend.

        Called by the WebSocket message handler when a BASH_CONFIRMATION_RESPONSE is received.

        Args:
            confirmation_id: The confirmation ID from the response
            approved: Whether the command was approved
            user_message: Optional message from user when rejecting

        Returns:
            bool: True if confirmation was found and processed, False otherwise
        """

        pending = self.pending_confirmations.get(confirmation_id)

        if pending is None:
            logger.warning(f"Received response for unknown confirmation: {confirmation_id}")
            return False

        if pending.future.done():
            logger.warning(f"Received duplicate response for confirmation: {confirmation_id}")
            return False

        # Set the result to wake up the waiting coroutine
        pending.future.set_result((approved, user_message))
        logger.info(f"Processed confirmation {confirmation_id}: {'approved' if approved else 'rejected'}")
        if user_message:
            logger.info(f"With user message: {user_message}")
        return True

    async def cleanup(self):
        """Clean up service resources."""
        # Reject all pending confirmations
        for pending in self.pending_confirmations.values():
            if not pending.future.done():
                pending.future.set_result((False, None))

        self.pending_confirmations.clear()

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