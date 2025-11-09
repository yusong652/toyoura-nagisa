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


def create_error_message(
    error: str,
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create error message.

    Args:
        error: Error description
        session_id: Session ID
        details: Additional error details

    Returns:
        Error message dictionary
    """
    msg = ErrorMessage(
        type=MessageType.ERROR,
        error_code="GENERAL_ERROR",
        error_message=error,
        session_id=session_id,
        details=details
    )
    return msg.model_dump(mode="json")


def create_tool_confirmation_request(
    tool_call_id: str,
    tool_name: str,
    command: str,
    description: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create tool confirmation request message (for bash, edit, write, etc.).

    Args:
        tool_call_id: ID of the tool call (used for both matching and tracking)
        tool_name: Name of the tool requiring confirmation (bash, edit, write)
        command: Command/operation to execute
        description: Command description (optional)
        session_id: Session ID

    Returns:
        Tool confirmation request message dictionary
    """
    msg = ToolConfirmationRequestMessage(
        type=MessageType.TOOL_CONFIRMATION_REQUEST,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        command=command,
        description=description,
        session_id=session_id
    )
    return msg.model_dump(mode="json", exclude_none=True)


def create_background_process_notification(
    message_type: MessageType,
    process_id: str,
    command: str,
    status: str,
    recent_output: List[str],
    runtime_seconds: float,
    description: Optional[str] = None,
    has_more_output: bool = False,
    exit_code: Optional[int] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create background process notification message.

    Args:
        message_type: Notification type (STARTED/OUTPUT_UPDATE/COMPLETED/KILLED)
        process_id: Unique process identifier
        command: Shell command being executed
        status: Process status ("running", "completed", "killed")
        recent_output: Last 5 lines of output for display
        runtime_seconds: Process runtime in seconds
        description: Optional command description
        has_more_output: Whether more output is available beyond recent_output
        exit_code: Process exit code when completed/killed
        session_id: Session ID

    Returns:
        Background process notification message dictionary
    """
    msg = BackgroundProcessNotification(
        type=message_type,
        process_id=process_id,
        command=command,
        description=description,
        status=status,
        recent_output=recent_output,
        has_more_output=has_more_output,
        runtime_seconds=runtime_seconds,
        exit_code=exit_code,
        session_id=session_id
    )
    return msg.model_dump(mode="json", exclude_none=True)
