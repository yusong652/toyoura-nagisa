"""
WebSocket Notification Service.

Centralized service for sending real-time notifications to frontend via WebSocket.
Handles all message-related notifications including streaming updates, message creation,
and message saved events.
"""

from typing import List, Dict, Any, Optional
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
        streaming: bool = True,
        usage: Optional[Dict[str, int]] = None
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
            usage: Optional token usage statistics
                - prompt_tokens: Input tokens (context window usage)
                - completion_tokens: Output tokens (AI response)
                - total_tokens: Total tokens used
                - tokens_left: Remaining tokens in context window

        Example:
            await WebSocketNotificationService.send_streaming_update(
                session_id="session-123",
                message_id="msg-456",
                content=[
                    {"type": "thinking", "thinking": "Complete thinking so far..."},
                    {"type": "text", "text": "Complete text so far..."}
                ],
                streaming=True,
                usage={
                    "prompt_tokens": 15420,
                    "completion_tokens": 850,
                    "total_tokens": 16270,
                    "tokens_left": 112580
                }
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
                streaming=streaming,
                usage=usage
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

    @staticmethod
    async def send_todo_update(
        session_id: str,
        todo: Optional[Dict[str, Any]]
    ) -> None:
        """
        Send todo status update notification to frontend.

        This notification tells the frontend about the current in_progress todo
        for real-time status display. Sent whenever the todo list is modified.

        Args:
            session_id: Session ID for which the todo was updated
            todo: Current in_progress todo item, or None if no in_progress todo
                Expected fields:
                - todo_id: str
                - content: str (imperative form)
                - activeForm: str (present continuous form)
                - status: str
                - session_id: str
                - created_at: float
                - updated_at: float
                - metadata: dict

        Example:
            await WebSocketNotificationService.send_todo_update(
                session_id="session-123",
                todo={
                    "todo_id": "a1b2c3d4",
                    "content": "Run tests",
                    "activeForm": "Running tests",
                    "status": "in_progress",
                    ...
                }
            )

        Note:
            Failures in WebSocket sending are logged but do not interrupt the process.
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            connection_manager = get_connection_manager()

            if not connection_manager:
                logger.debug("No connection manager available for todo update notification")
                return

            # Create todo update notification
            todo_update_msg = {
                "type": "TODO_UPDATE",
                "session_id": session_id,
                "todo": todo
            }

            # Send via WebSocket
            await connection_manager.send_json(session_id, todo_update_msg)

            if todo:
                logger.debug(f"Todo update notification sent for session {session_id}: {todo.get('activeForm')}")
            else:
                logger.debug(f"Todo cleared notification sent for session {session_id}")

        except Exception as e:
            logger.warning(f"Failed to send todo update notification: {e}")
            # Don't re-raise - this is a non-critical notification

    @staticmethod
    async def send_tool_result_update(
        session_id: str,
        message_id: str,
        tool_call_id: str,
        tool_name: str,
        tool_result: Dict[str, Any]
    ) -> None:
        """
        Send tool result update notification to frontend for real-time display.

        This notification sends the complete tool result content so frontends
        can display it immediately without needing to refresh from API.
        The format matches the database storage format for consistency.

        Args:
            session_id: Target session ID
            message_id: ID of the saved tool result message
            tool_call_id: ID of the tool call this result corresponds to
            tool_name: Name of the executed tool
            tool_result: Tool execution result (ToolResult format with llm_content)

        Example:
            await WebSocketNotificationService.send_tool_result_update(
                session_id="session-123",
                message_id="msg-456",
                tool_call_id="call_789",
                tool_name="read_file",
                tool_result={
                    "status": "success",
                    "message": "File read successfully",
                    "llm_content": {"parts": [{"type": "text", "text": "..."}]}
                }
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
                logger.debug("Connection manager not available for TOOL_RESULT_UPDATE")
                return

            # Extract content from tool result (same format as database storage)
            llm_content = tool_result.get("llm_content", {})

            # Build tool_result content block matching database format
            tool_result_content = {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "tool_name": tool_name,
                "content": llm_content,
                "is_error": tool_result.get("status") == "error"
            }

            # Send TOOL_RESULT_UPDATE notification
            notification = {
                'type': 'TOOL_RESULT_UPDATE',
                'message_id': message_id,
                'session_id': session_id,
                'content': [tool_result_content]  # Array format matching Message.content
            }

            success = await connection_manager.send_json(session_id, notification)

            if success:
                logger.debug(f"Sent TOOL_RESULT_UPDATE for tool {tool_name} in session {session_id}")
            else:
                logger.debug(f"Failed to send TOOL_RESULT_UPDATE (no connection for session {session_id})")

        except Exception as e:
            logger.warning(f"Failed to send tool result update notification: {e}")
            # Don't re-raise - this is a non-critical notification
