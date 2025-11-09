"""
Message factory functions and schema registries.

This module provides factory functions for creating WebSocket messages
and schema registries for validating incoming/outgoing messages.
"""
import json
from typing import Dict, Any, Optional, List

from backend.presentation.websocket.messages.types import MessageType
from backend.presentation.websocket.messages.base import BaseWebSocketMessage

# Import all message classes
from backend.presentation.websocket.messages.connection import HeartbeatMessage
from backend.presentation.websocket.messages.location import (
    LocationRequestMessage,
    LocationResponseMessage
)
from backend.presentation.websocket.messages.emotion import EmotionKeywordMessage
from backend.presentation.websocket.messages.tts import TTSChunk
from backend.presentation.websocket.messages.system import (
    ErrorMessage,
    StatusUpdate,
    TitleUpdateMessage
)
from backend.presentation.websocket.messages.queue import (
    QueueUpdateMessage,
    ProcessingStartMessage,
    MessageQueuedMessage
)
from backend.presentation.websocket.messages.background_process import BackgroundProcessNotification
from backend.presentation.websocket.messages.tool import (
    ToolConfirmationRequestMessage,
    ToolConfirmationResponseMessage,
    UserInterruptMessage
)
from backend.presentation.websocket.messages.chat import (
    ChatMessageRequest,
    MessageCreateMessage,
    StreamingUpdateMessage
)


# Incoming message schemas (messages that frontend sends to backend)
INCOMING_MESSAGE_SCHEMAS = {
    MessageType.HEARTBEAT_ACK: HeartbeatMessage,
    MessageType.LOCATION_RESPONSE: LocationResponseMessage,
    MessageType.CHAT_MESSAGE: ChatMessageRequest,
    MessageType.TOOL_CONFIRMATION_RESPONSE: ToolConfirmationResponseMessage,
    MessageType.USER_INTERRUPT: UserInterruptMessage,
}

# Outgoing message schemas (backend creates these messages to send to frontend)
# Only includes message types that are actually used in the codebase
OUTGOING_MESSAGE_SCHEMAS = {
    # Used via create_message()
    MessageType.EMOTION_KEYWORD: EmotionKeywordMessage,
    MessageType.ERROR: ErrorMessage,
    MessageType.MESSAGE_CREATE: MessageCreateMessage,
    MessageType.STATUS_UPDATE: StatusUpdate,
    MessageType.TITLE_UPDATE: TitleUpdateMessage,
    MessageType.TTS_CHUNK: TTSChunk,
    MessageType.STREAMING_UPDATE: StreamingUpdateMessage,  # Real-time content update (accumulated)
    # Used via specialized creation functions
    MessageType.TOOL_CONFIRMATION_REQUEST: ToolConfirmationRequestMessage,
    # Background process notifications
    MessageType.BACKGROUND_PROCESS_STARTED: BackgroundProcessNotification,
    MessageType.BACKGROUND_PROCESS_OUTPUT_UPDATE: BackgroundProcessNotification,
    MessageType.BACKGROUND_PROCESS_COMPLETED: BackgroundProcessNotification,
    MessageType.BACKGROUND_PROCESS_KILLED: BackgroundProcessNotification,
    # Message queue notifications
    MessageType.QUEUE_UPDATE: QueueUpdateMessage,
    MessageType.PROCESSING_START: ProcessingStartMessage,
    MessageType.MESSAGE_QUEUED: MessageQueuedMessage,
}


def create_message(message_type: MessageType, **kwargs) -> BaseWebSocketMessage:
    """
    Create a typed WebSocket message instance.

    Args:
        message_type: Type of message to create
        **kwargs: Message-specific parameters

    Returns:
        BaseWebSocketMessage: Typed message instance

    Example:
        msg = create_message(MessageType.CHAT_MESSAGE,
                           message="Hello", stream_response=True)
    """
    schema_class = OUTGOING_MESSAGE_SCHEMAS.get(message_type, BaseWebSocketMessage)
    return schema_class(type=message_type, **kwargs)


def parse_incoming_websocket_message(data: str) -> BaseWebSocketMessage:
    """
    Parse incoming WebSocket message data from frontend into typed message object.

    Frontend sends JSON strings via WebSocket which are parsed here into typed objects.

    Args:
        data: JSON string from frontend WebSocket message (event.data)

    Returns:
        BaseWebSocketMessage: Typed message instance for routing to handlers

    Raises:
        ValueError: If message format is invalid or type is unsupported

    Example:
        # From WebSocket handler
        raw_message = '{"type": "CHAT_MESSAGE", "message": "Hello"}'
        message = parse_incoming_websocket_message(raw_message)

    Note:
        This function specifically handles messages FROM frontend TO backend.
        For outgoing messages, use create_message() instead.
    """
    # Parse JSON string from WebSocket
    try:
        parsed_data = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in WebSocket message: {e}")

    # Validate basic message structure
    if not isinstance(parsed_data, dict) or "type" not in parsed_data:
        raise ValueError("WebSocket message must be JSON object with 'type' field")

    # Validate message type
    try:
        message_type = MessageType(parsed_data["type"])
    except ValueError:
        raise ValueError(f"Unsupported WebSocket message type: {parsed_data['type']}")

    # Use incoming-specific schemas for validation (more restrictive)
    schema_class = INCOMING_MESSAGE_SCHEMAS.get(message_type)
    if not schema_class:
        raise ValueError(f"Message type '{message_type}' not accepted from frontend")

    # Parse and validate message data
    try:
        return schema_class(**parsed_data)
    except Exception as e:
        raise ValueError(f"Invalid message format for '{message_type}': {e}")
