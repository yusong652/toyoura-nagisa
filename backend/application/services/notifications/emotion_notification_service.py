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


def get_emotion_notification_service() -> Optional[EmotionNotificationService]:
    """
    Get emotion notification service from WebSocketHandler.

    Returns:
        EmotionNotificationService instance or None if not initialized

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
        if not hasattr(handler, 'emotion_service'):
            logger.warning("Emotion notification service not found in WebSocket handler")
            return None

        return handler.emotion_service

    except Exception as e:
        logger.warning(f"Could not get emotion notification service: {e}")
        return None