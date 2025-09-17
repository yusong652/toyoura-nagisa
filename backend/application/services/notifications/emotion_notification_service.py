"""
Emotion Notification Application Service - DDD Application Layer

This service handles emotion keyword notifications for Live2D animation triggers
by coordinating between business logic and WebSocket infrastructure.

DDD Role: Application Service
- Implements emotion notification use cases for Live2D animations
- Uses ConnectionManager (infrastructure) for WebSocket delivery
- Contains business logic for emotion keyword processing
"""
import logging
from typing import Optional
from backend.infrastructure.websocket.connection_manager import ConnectionManager
from backend.presentation.websocket.message_types import MessageType, create_message

logger = logging.getLogger(__name__)


class EmotionNotificationService:
    """
    Application Service for Live2D Emotion Notifications.

    Coordinates emotion keyword notification use cases for Live2D animation triggers.
    Handles real-time emotion keyword delivery to frontend for character animations.

    Uses ConnectionManager (infrastructure layer) for actual WebSocket delivery.
    """

    def __init__(self, connection_manager: ConnectionManager):
        """
        Initialize emotion notification service.

        Args:
            connection_manager: WebSocket connection manager instance
        """
        self.connection_manager = connection_manager

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

            # Send via WebSocket if connection exists
            if await self.connection_manager.is_connected(session_id):
                await self.connection_manager.send_json(
                    session_id,
                    message.model_dump()
                )
                logger.debug(f"Sent emotion keyword notification: {keyword} for session {session_id}")
            else:
                logger.warning(
                    f"Cannot send emotion keyword - session {session_id} not connected"
                )

        except Exception as e:
            logger.error(f"Failed to send emotion keyword notification: {e}")


# Global service instance
_emotion_service: Optional[EmotionNotificationService] = None


def get_emotion_notification_service(
    connection_manager: Optional[ConnectionManager] = None
) -> Optional[EmotionNotificationService]:
    """
    Get or initialize the global emotion notification service.

    Args:
        connection_manager: Optional connection manager for initialization.
                          If provided, initializes a new service instance.
                          If None, returns existing global instance.

    Returns:
        EmotionNotificationService instance or None if not initialized

    Usage:
        # Initialize (typically in application startup)
        service = get_emotion_notification_service(connection_manager)

        # Get existing instance (in business logic)
        service = get_emotion_notification_service()
    """
    global _emotion_service

    if connection_manager:
        # Initialize new service instance
        _emotion_service = EmotionNotificationService(connection_manager)
        return _emotion_service
    elif _emotion_service is None:
        # Try to auto-initialize with global connection manager
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager, ConnectionManager
            global_manager = get_connection_manager()
            if global_manager is not None:
                _emotion_service = EmotionNotificationService(global_manager)
            else:
                # Fallback to creating a new instance
                _emotion_service = EmotionNotificationService(ConnectionManager())
        except Exception as e:
            logger.warning(f"Could not initialize emotion service: {e}")

    return _emotion_service