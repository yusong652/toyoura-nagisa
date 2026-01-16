"""
WebSocket message sender for outgoing messages to frontend.

This module provides utilities for sending WebSocket messages from backend to frontend,
including message creation notifications.

Responsibilities:
- Format and send MESSAGE_CREATE events
- Handle WebSocket connection state checks
- Provide error handling for message sending failures
"""

import logging

from backend.infrastructure.websocket.connection_manager import get_connection_manager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


async def send_message_create(
    session_id: str,
    message_id: str
) -> None:
    """
    Send MESSAGE_CREATE event via WebSocket to create a new bot message.

    Notifies frontend to create a new bot message with the specified ID.

    Args:
        session_id: WebSocket session ID
        message_id: ID for the new message to create

    Returns:
        None: Silently fails if WebSocket is unavailable
    """
    try:
        connection_manager = get_connection_manager()

        if not connection_manager or not connection_manager.is_connected_sync(session_id):
            logger.debug(f"No WebSocket connection for session {session_id}, skipping MESSAGE_CREATE")
            return

        # Create MESSAGE_CREATE message
        create_message_msg = create_message(
            MessageType.MESSAGE_CREATE,
            session_id=session_id,
            message_id=message_id,
            role="assistant",
            initial_text="",
            streaming=True
        )

        # Send to WebSocket client
        await connection_manager.send_json(session_id, create_message_msg.model_dump())

    except Exception as e:
        # Don't break the main flow if WebSocket sending fails
        logger.warning(f"Failed to send MESSAGE_CREATE via WebSocket to session {session_id}: {e}")
