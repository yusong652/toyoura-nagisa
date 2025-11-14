"""
WebSocket Notification Service.

Centralized service for sending real-time notifications to frontend via WebSocket.
Handles all message-related notifications including streaming updates, message creation,
and message saved events.
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class WebSocketNotificationService:
    """
    Centralized WebSocket notification service.

    Provides static methods for sending various types of real-time notifications
    to the frontend via WebSocket connections. Handles errors gracefully to ensure
    WebSocket failures don't interrupt core business logic.
    """

    @staticmethod
    async def send_streaming_update(
        session_id: str,
        message_id: str,
        content: List[Dict[str, Any]],
        streaming: bool = True
    ) -> None:
        """
        Send accumulated content update to WebSocket for real-time display.

        This method sends complete accumulated content blocks instead of individual chunks,
        making frontend logic simpler and consistent with session refresh data structure.

        The frontend receives complete thinking/text content and simply replaces message content,
        ensuring data structure consistency between real-time streaming and database storage.

        Args:
            session_id: Target session ID
            message_id: Message ID to update
            content: Complete content blocks array [{"type": "thinking", "thinking": "..."}, ...]
            streaming: Whether message is still streaming (True) or complete (False)

        Example:
            await WebSocketNotificationService.send_streaming_update(
                session_id="session-123",
                message_id="msg-456",
                content=[
                    {"type": "thinking", "thinking": "Complete thinking so far..."},
                    {"type": "text", "text": "Complete text so far..."}
                ],
                streaming=True
            )

        Note:
            Failures in WebSocket sending are logged but do not interrupt the process.
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            connection_manager = get_connection_manager()

            if not connection_manager:
                return

            # Construct WebSocket message
            from backend.presentation.websocket.message_types import MessageType, create_message

            ws_message = create_message(
                MessageType.STREAMING_UPDATE,
                session_id=session_id,
                message_id=message_id,
                content=content,
                streaming=streaming
            )

            await connection_manager.send_json(session_id, ws_message.model_dump())

        except Exception as e:
            # Streaming display failure should not interrupt main flow
            logger.warning(f"Failed to send streaming update to WebSocket: {e}")

    @staticmethod
    async def send_message_create(
        session_id: str,
        message_id: str,
        streaming: bool = True,
        initial_text: str = ""
    ) -> None:
        """
        Send MESSAGE_CREATE notification to frontend to create message container.

        This notification tells the frontend to create a new message placeholder
        before streaming content begins. The message container will receive
        streaming updates via STREAMING_UPDATE messages.

        Args:
            session_id: Target session ID
            message_id: ID of the created message
            streaming: Whether this message will receive streaming updates
            initial_text: Optional initial text content

        Example:
            await WebSocketNotificationService.send_message_create(
                session_id="session-123",
                message_id="msg-456",
                streaming=True
            )

        Note:
            Failures in WebSocket sending are logged but do not interrupt the process.
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            connection_manager = get_connection_manager()

            if not connection_manager:
                return

            from backend.presentation.websocket.message_types import MessageType, create_message

            ws_message = create_message(
                MessageType.MESSAGE_CREATE,
                session_id=session_id,
                message_id=message_id,
                role="assistant",
                initial_text=initial_text,
                streaming=streaming
            )

            await connection_manager.send_json(session_id, ws_message.model_dump())

        except Exception as e:
            logger.warning(f"Failed to send message create notification: {e}")

    @staticmethod
    async def send_message_saved(
        session_id: str,
        message_id: str,
        role: str
    ) -> None:
        """
        Send notification that a message was saved to database.

        This triggers frontend to refresh and display the new message immediately.

        Args:
            session_id: Target session ID
            message_id: ID of the saved message
            role: Message role ('user' for tool_result, 'assistant' for tool_use)

        Example:
            await WebSocketNotificationService.send_message_saved(
                session_id="session-123",
                message_id="msg-456",
                role="user"
            )

        Note:
            Failures in WebSocket sending are logged but do not interrupt the process.
        """
        if not session_id:
            return

        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager

            connection_manager = get_connection_manager()
            if not connection_manager:
                logger.debug("Connection manager not available for MESSAGE_SAVED")
                return

            # Send custom event to trigger message refresh
            notification = {
                'type': 'MESSAGE_SAVED',
                'message_id': message_id,
                'role': role,
                'session_id': session_id
            }

            # Send via WebSocket to trigger frontend message refresh
            success = await connection_manager.send_json(session_id, notification)

            if success:
                logger.debug(f"Sent MESSAGE_SAVED notification for {role} message {message_id}")
            else:
                logger.debug(f"Failed to send MESSAGE_SAVED notification (no connection for session {session_id})")

        except Exception as e:
            logger.debug(f"Failed to send message saved notification: {e}")

    @staticmethod
    async def send_title_update(
        session_id: str,
        new_title: str
    ) -> None:
        """
        Send session title update notification to frontend.

        This notification tells the frontend to update the session title
        in the sidebar without requiring a full session list refresh.

        Args:
            session_id: Session ID for which the title was updated
            new_title: The new title for the session

        Example:
            await WebSocketNotificationService.send_title_update(
                session_id="session-123",
                new_title="Discussion about Python"
            )

        Note:
            Failures in WebSocket sending are logged but do not interrupt the process.
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            connection_manager = get_connection_manager()

            if not connection_manager:
                logger.warning("No connection manager available for title update notification")
                return

            # Create title update message
            from backend.presentation.websocket.message_types import MessageType, create_message

            title_update_msg = create_message(
                MessageType.TITLE_UPDATE,
                session_id=session_id,
                payload={
                    "session_id": session_id,
                    "title": new_title
                }
            )

            # Send via WebSocket
            await connection_manager.send_json(
                session_id,
                title_update_msg.model_dump()
            )

            logger.info(f"Title update notification sent for session {session_id}: {new_title}")

        except Exception as e:
            logger.error(f"Failed to send title update notification: {e}")
            # Don't re-raise - this is a non-critical notification
