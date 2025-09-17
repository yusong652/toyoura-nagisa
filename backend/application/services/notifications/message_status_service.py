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



# Global service instance
_status_service: Optional[MessageStatusService] = None


def get_message_status_service(
    connection_manager: Optional[ConnectionManager] = None
) -> Optional[MessageStatusService]:
    """
    Get or initialize the global message status service.

    Args:
        connection_manager: Optional connection manager for initialization.
                          If provided, initializes a new service instance.
                          If None, returns existing global instance.

    Returns:
        MessageStatusService instance or None if not initialized

    Usage:
        # Initialize (typically in application startup)
        service = get_message_status_service(connection_manager)

        # Get existing instance (in business logic)
        service = get_message_status_service()
    """
    global _status_service

    if connection_manager:
        # Initialize new service instance
        _status_service = MessageStatusService(connection_manager)
        return _status_service
    elif _status_service is None:
        # Try to auto-initialize with global connection manager
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager, ConnectionManager
            global_manager = get_connection_manager()
            if global_manager is not None:
                _status_service = MessageStatusService(global_manager)
            else:
                # Fallback to creating a new instance
                _status_service = MessageStatusService(ConnectionManager())
        except Exception as e:
            logger.warning(f"Could not initialize status service: {e}")

    return _status_service
