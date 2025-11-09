"""
WebSocket message type definitions and schemas.

This module defines all supported WebSocket message types and their
corresponding data structures for the aiNagisa real-time communication system.

DEPRECATED: This module is being refactored. Please import from:
- backend.presentation.websocket.messages for core types
- Specific message schema modules will be added progressively

Architecture Overview:
- Frontend sends JSON strings via WebSocket: ws.send(JSON.stringify(message))
- Backend receives as event.data (string) or pre-parsed dict (framework-dependent)
- parse_incoming_websocket_message() handles both formats
- Only specific message types are accepted from frontend (INCOMING_MESSAGE_SCHEMAS)
- Backend-to-frontend messages use create_message() for consistent formatting
"""
from typing import Any, Dict, List, Optional

# Import core types from new modular structure
from backend.presentation.websocket.messages import MessageType, BaseWebSocketMessage
from backend.presentation.websocket.messages.connection import HeartbeatMessage
from backend.presentation.websocket.messages.location import (
    LocationRequestMessage,
    LocationResponseMessage
)
from backend.presentation.websocket.messages.emotion import EmotionKeywordMessage
from backend.presentation.websocket.messages.tts import TTSChunk


class ChatMessageRequest(BaseWebSocketMessage):
    """Chat message request schema"""
    type: MessageType = MessageType.CHAT_MESSAGE
    message: str
    context: Optional[Dict[str, Any]] = None
    stream_response: bool = True
    agent_profile: str = "general"
    enable_memory: bool = True
    tts_enabled: bool = False
    files: List[Dict[str, Any]] = []


class ChatStreamChunk(BaseWebSocketMessage):
    """Chat stream chunk message schema"""
    type: MessageType = MessageType.CHAT_STREAM_CHUNK
    content: str
    chunk_type: str = "text"  # text, tool_call, status, etc.
    is_final: bool = False


class ToolUseNotification(BaseWebSocketMessage):
    """Tool use notification message schema"""
    type: MessageType  # Will be NAGISA_IS_USING_TOOL or NAGISA_TOOL_USE_CONCLUDED
    tool_names: Optional[List[str]] = None
    action: Optional[str] = None
    thinking: Optional[str] = None
    results: Optional[Dict[str, Any]] = None


class ErrorMessage(BaseWebSocketMessage):
    """Error message schema"""
    type: MessageType = MessageType.ERROR
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None


class StatusUpdate(BaseWebSocketMessage):
    """Status update message schema"""
    type: MessageType = MessageType.STATUS_UPDATE
    status: str
    data: Optional[Dict[str, Any]] = None


class MessageCreateMessage(BaseWebSocketMessage):
    """Message creation message schema for dynamic bot message creation"""
    type: MessageType = MessageType.MESSAGE_CREATE
    role: str = "assistant"  # "user" | "assistant" | "system"
    initial_text: Optional[str] = None
    streaming: bool = True


class ToolConfirmationRequestMessage(BaseWebSocketMessage):
    """Tool confirmation request message schema (for bash, edit, write, etc.)"""
    type: MessageType = MessageType.TOOL_CONFIRMATION_REQUEST
    tool_call_id: str  # ID of the tool call to match with frontend ToolUseBlock
    tool_name: str
    command: str
    description: Optional[str] = None


class ToolConfirmationResponseMessage(BaseWebSocketMessage):
    """Tool confirmation response message schema"""
    type: MessageType = MessageType.TOOL_CONFIRMATION_RESPONSE
    tool_call_id: str  # ID of the tool call to match the request
    approved: bool
    user_message: Optional[str] = None


class UserInterruptMessage(BaseWebSocketMessage):
    """User interrupt message schema (ESC key pressed)"""
    type: MessageType = MessageType.USER_INTERRUPT


class TitleUpdateMessage(BaseWebSocketMessage):
    """Title update message schema for session title changes"""
    type: MessageType = MessageType.TITLE_UPDATE
    payload: Dict[str, Any]  # Contains session_id and title


class BackgroundProcessNotification(BaseWebSocketMessage):
    """
    Background process notification message schema for frontend display.

    Provides real-time updates about background bash processes with recent output
    for user monitoring. Designed to show command name and last 5 lines of output
    in a compact UI panel.
    """
    type: MessageType
    process_id: str
    command: str
    description: Optional[str] = None
    status: str  # "running", "completed", "killed"

    # Recent output for display (last 5 lines)
    recent_output: List[str] = []
    has_more_output: bool = False

    # Statistics
    runtime_seconds: float = 0
    exit_code: Optional[int] = None


class StreamingChunkMessage(BaseWebSocketMessage):
    """
    Streaming chunk message for real-time thinking/text display.

    Provides real-time streaming of LLM response chunks including thinking
    content, text generation, and function calls. Enables progressive display
    of AI reasoning and response generation.

    Attributes:
        chunk_type: Type of content ("thinking", "text", "function_call")
        content: The actual text content of this chunk
        metadata: Additional context (e.g., has_signature, args for function calls)
    """
    type: MessageType = MessageType.STREAMING_CHUNK
    chunk_type: str  # "thinking" | "text" | "function_call"
    content: str
    metadata: Dict[str, Any] = {}


class StreamingUpdateMessage(BaseWebSocketMessage):
    """
    Streaming update message for real-time content display with accumulated content.

    Sends complete accumulated content blocks instead of individual chunks,
    making frontend logic simpler and consistent with session refresh data structure.
    Frontend receives complete thinking/text content and simply replaces message content.

    This approach ensures data structure consistency between:
    - Real-time streaming (accumulated content blocks)
    - Stored messages (content[] array format)
    - Session refresh (loads content[] from database)

    Attributes:
        content: Complete content blocks array [{"type": "thinking", "thinking": "..."}, ...]
        streaming: Whether message is still streaming (true) or complete (false)

    Example:
        {
            "type": "STREAMING_UPDATE",
            "message_id": "msg-123",
            "session_id": "session-456",
            "content": [
                {"type": "thinking", "thinking": "Current complete thinking content..."},
                {"type": "text", "text": "Current complete text content..."}
            ],
            "streaming": true
        }
    """
    type: MessageType = MessageType.STREAMING_UPDATE
    content: List[Dict[str, Any]]  # ContentBlock array: [{"type": "thinking", "thinking": "..."}, ...]
    streaming: bool = True


class QueueUpdateMessage(BaseWebSocketMessage):
    """
    Queue update message for notifying frontend about message queue status.

    Provides real-time updates about the session's message queue, including
    number of pending messages and processing state.

    Attributes:
        payload: Queue status information
            - queue_size: Number of messages waiting in queue
            - is_processing: Whether session is currently processing
            - timestamp: Update timestamp
    """
    type: MessageType = MessageType.QUEUE_UPDATE
    payload: Dict[str, Any]


class ProcessingStartMessage(BaseWebSocketMessage):
    """
    Processing start message for notifying frontend when message processing begins.

    Sent when a message is taken from the queue and processing starts,
    allowing frontend to show "processing" status.

    Attributes:
        payload: Processing information
            - remaining_in_queue: Number of messages still waiting
            - timestamp: Processing start timestamp
    """
    type: MessageType = MessageType.PROCESSING_START
    payload: Dict[str, Any]


class MessageQueuedMessage(BaseWebSocketMessage):
    """
    Message queued notification for frontend confirmation.

    Sent immediately after a user message is successfully added to the queue,
    providing feedback that the message was received and will be processed.

    Attributes:
        payload: Queue information
            - position: Position in queue (0 = processing now, 1+ = waiting)
            - queue_size: Total queue size
            - timestamp: Queued timestamp
    """
    type: MessageType = MessageType.MESSAGE_QUEUED
    payload: Dict[str, Any]


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
    MessageType.CHAT_STREAM_CHUNK: ChatStreamChunk,
    MessageType.EMOTION_KEYWORD: EmotionKeywordMessage,
    MessageType.ERROR: ErrorMessage,
    MessageType.MESSAGE_CREATE: MessageCreateMessage,
    MessageType.NAGISA_IS_USING_TOOL: ToolUseNotification,
    MessageType.NAGISA_TOOL_USE_CONCLUDED: ToolUseNotification,
    MessageType.STATUS_UPDATE: StatusUpdate,
    MessageType.TITLE_UPDATE: TitleUpdateMessage,
    MessageType.TTS_CHUNK: TTSChunk,
    MessageType.STREAMING_CHUNK: StreamingChunkMessage,  # Real-time thinking/text streaming (legacy)
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
    import json
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
    """Create error message

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


def create_tool_use_message(
    is_using: bool,
    tool_name: Optional[str] = None,
    action: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create tool use message

    Args:
        is_using: Whether currently using tool
        tool_name: Tool name
        action: Action description
        result: Tool result
        session_id: Session ID

    Returns:
        Tool use message dictionary
    """
    msg_type = MessageType.NAGISA_IS_USING_TOOL if is_using else MessageType.NAGISA_TOOL_USE_CONCLUDED

    msg = ToolUseNotification(
        type=msg_type,
        tool_names=[tool_name] if tool_name else None,
        action=action,
        results=result,
        session_id=session_id
    )
    return msg.model_dump(mode="json", exclude_none=True)


def create_tool_confirmation_request(
    tool_call_id: str,
    tool_name: str,
    command: str,
    description: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create tool confirmation request message (for bash, edit, write, etc.)

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