"""
Message status notification service for WebSocket.

This module provides centralized message status update functionality,
enabling real-time status notifications for message lifecycle events.
"""
import logging
from typing import Optional
from backend.presentation.websocket.connection import ConnectionManager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


class MessageStatusNotificationService:
    """
    Service for sending message status updates via WebSocket.
    
    Provides real-time notifications for message lifecycle events:
    - sending: Message is being sent
    - sent: Message received by backend
    - read: Message is being processed by LLM
    - error: Message processing failed
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

    async def notify_emotion_keyword(
        self,
        session_id: str,
        keyword: str,
        message_id: Optional[str] = None
    ) -> None:
        """
        Notify about emotion keyword for Live2D animation triggers.

        Args:
            session_id: Session identifier
            keyword: Emotion keyword (e.g., "happy", "sad", "excited")
            message_id: Optional message identifier
        """
        try:
            message = create_message(
                MessageType.EMOTION_KEYWORD,
                session_id=session_id,
                keyword=keyword,
                message_id=message_id
            )
            await self.connection_manager.send_json(session_id, message.model_dump())
            logger.debug(f"Sent emotion keyword notification: {keyword} for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to send emotion keyword notification: {e}")


# Global instance for easy access
_status_service: Optional[MessageStatusNotificationService] = None


def get_status_notification_service(
    connection_manager: Optional[ConnectionManager] = None
) -> Optional[MessageStatusNotificationService]:
    """
    Get or create the global status notification service.

    Args:
        connection_manager: Connection manager to use for new instance

    Returns:
        MessageStatusNotificationService instance or None if not initialized
    """
    global _status_service

    if connection_manager:
        print(f"[STATUS_SERVICE] Creating new status service with provided connection manager")
        _status_service = MessageStatusNotificationService(connection_manager)
    elif _status_service is None:
        # Try to get connection manager from WebSocket handler
        try:
            from backend.presentation.websocket.websocket_handler import get_websocket_handler
            handler = get_websocket_handler()
            if handler and handler.connection_manager:
                print(f"[STATUS_SERVICE] Creating status service with handler's connection manager")
                _status_service = MessageStatusNotificationService(handler.connection_manager)
            else:
                print(f"[STATUS_SERVICE] WARNING: WebSocket handler or connection manager not available")
        except Exception as e:
            print(f"[STATUS_SERVICE] WARNING: Could not initialize status service: {e}")
    else:
        print(f"[STATUS_SERVICE] Using existing status service instance")

    if _status_service is None:
        print(f"[STATUS_SERVICE] ERROR: Status service could not be initialized")

    return _status_service