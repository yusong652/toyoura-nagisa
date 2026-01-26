"""
Message Status Application Service - DDD Application Layer

This service handles message status notification use cases by coordinating
between business logic and WebSocket infrastructure.

DDD Role: Application Service
- Implements message status notification use cases
- Uses ConnectionManager (infrastructure) for WebSocket delivery
- Contains business logic for different status types
"""
import logging
from typing import Optional
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


class MessageStatusService:
    """
    Application Service for Message Status Notifications.

    Coordinates message status notification use cases:
    - sending: Message is being sent
    - sent: Message received by backend
    - read: Message is being processed by LLM
    - error: Message processing failed

    Uses ConnectionManager (infrastructure layer) for actual WebSocket delivery.
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize status notification service.
        
        Args:
            connection_manager: WebSocket connection manager instance
        """
        self.connection_manager = connection_manager
    
    async def notify_status(
        self,
        session_id: str,
        message_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Send message status update via WebSocket.

        Args:
            session_id: WebSocket session ID
            message_id: ID of the message being updated
            status: Status to set ("sending", "sent", "read", "error")
            error_message: Optional error details when status is "error"
        """
        try:
            # Create status update message
            status_msg = create_message(
                MessageType.STATUS_UPDATE,
                session_id=session_id,
                message_id=message_id,
                status=status,
                error_message=error_message
            )

            # Send via WebSocket if connection exists
            if await self.connection_manager.is_connected(session_id):
                await self.connection_manager.send_json(
                    session_id,
                    status_msg.model_dump()
                )
            else:
                logger.warning(
                    f"Cannot send status update - session {session_id} not connected"
                )
                
        except Exception as e:
            logger.error(
                f"Failed to send status update for message {message_id}: {e}"
            )
    
    async def notify_sending(self, session_id: str, message_id: str) -> None:
        """Notify that message is being sent."""
        await self.notify_status(session_id, message_id, "sending")
    
    async def notify_sent(self, session_id: str, message_id: str) -> None:
        """Notify that message was received by backend."""
        await self.notify_status(session_id, message_id, "sent")
    
    async def notify_read(self, session_id: str, message_id: str) -> None:
        """Notify that message is being processed by LLM."""
        await self.notify_status(session_id, message_id, "read")
    
    async def notify_error(
        self,
        session_id: str,
        message_id: str,
        error_message: str
    ) -> None:
        """Notify that message processing failed."""
        await self.notify_status(session_id, message_id, "error", error_message)

def get_message_status_service() -> Optional[MessageStatusService]:
    """
    Get message status service from WebSocketHandler.

    Returns:
        MessageStatusService instance or None if not initialized

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
        if not hasattr(handler, 'status_service'):
            logger.warning("Message status service not found in WebSocket handler")
            return None

        return handler.status_service

    except Exception as e:
        logger.warning(f"Could not get message status service: {e}")
        return None
