"""
WebSocket message type definitions and schemas.

This module defines all supported WebSocket message types and their
corresponding data structures for the aiNagisa real-time communication system.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel
from datetime import datetime


class MessageType(str, Enum):
    """WebSocket message type enumeration"""
    # Connection management
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    CONNECTION_ESTABLISHED = "CONNECTION_ESTABLISHED"
    
    # Location services
    LOCATION_REQUEST = "LOCATION_REQUEST"
    LOCATION_RESPONSE = "LOCATION_RESPONSE"
    
    # Chat and streaming
    CHAT_MESSAGE = "CHAT_MESSAGE"
    CHAT_STREAM_START = "CHAT_STREAM_START"
    CHAT_STREAM_CHUNK = "CHAT_STREAM_CHUNK"
    CHAT_STREAM_END = "CHAT_STREAM_END"
    
    
    # Tool use notifications (for frontend display)
    NAGISA_IS_USING_TOOL = "NAGISA_IS_USING_TOOL"
    NAGISA_TOOL_USE_CONCLUDED = "NAGISA_TOOL_USE_CONCLUDED"
    
    # File operations
    FILE_UPLOAD_START = "FILE_UPLOAD_START"
    FILE_UPLOAD_CHUNK = "FILE_UPLOAD_CHUNK"
    FILE_UPLOAD_COMPLETE = "FILE_UPLOAD_COMPLETE"
    
    # System messages
    ERROR = "ERROR"
    STATUS_UPDATE = "STATUS_UPDATE"
    
    # TTS streaming
    TTS_CHUNK = "TTS_CHUNK"

    # Message management
    MESSAGE_CREATE = "MESSAGE_CREATE"

    # Emotion and animation
    EMOTION_KEYWORD = "EMOTION_KEYWORD"

    # Session management
    TITLE_UPDATE = "TITLE_UPDATE"

    # Bash command confirmation
    BASH_CONFIRMATION_REQUEST = "BASH_CONFIRMATION_REQUEST"
    BASH_CONFIRMATION_RESPONSE = "BASH_CONFIRMATION_RESPONSE"

    # Future extensions
    VOICE_MESSAGE = "VOICE_MESSAGE"
    IMAGE_GENERATION = "IMAGE_GENERATION"


class BaseWebSocketMessage(BaseModel):
    """Base WebSocket message schema"""
    type: MessageType
    session_id: Optional[str] = None
    timestamp: str = datetime.now().isoformat()
    message_id: Optional[str] = None


class HeartbeatMessage(BaseWebSocketMessage):
    """Heartbeat message schema"""
    type: MessageType = MessageType.HEARTBEAT



class LocationRequestMessage(BaseWebSocketMessage):
    """Location request message schema"""
    type: MessageType = MessageType.LOCATION_REQUEST
    request_id: str
    accuracy_level: str = "high"  # high, medium, low


class LocationResponseMessage(BaseWebSocketMessage):
    """Location response message schema"""
    type: MessageType = MessageType.LOCATION_RESPONSE
    request_id: Optional[str] = None
    location_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


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


class TTSChunk(BaseWebSocketMessage):
    """TTS chunk message schema for real-time audio streaming"""
    type: MessageType = MessageType.TTS_CHUNK
    text: str
    audio: Optional[str] = None  # Base64 encoded audio data
    index: int
    processing_time: Optional[float] = None
    engine_status: Optional[str] = None
    error: Optional[str] = None
    is_final: bool = False


class MessageCreateMessage(BaseWebSocketMessage):
    """Message creation message schema for dynamic bot message creation"""
    type: MessageType = MessageType.MESSAGE_CREATE
    sender: str = "bot"
    initial_text: Optional[str] = None
    streaming: bool = True


class EmotionKeywordMessage(BaseWebSocketMessage):
    """Emotion keyword message schema for Live2D animation triggers"""
    type: MessageType = MessageType.EMOTION_KEYWORD
    keyword: str
    message_id: Optional[str] = None


class BashConfirmationRequestMessage(BaseWebSocketMessage):
    """Bash command confirmation request message schema"""
    type: MessageType = MessageType.BASH_CONFIRMATION_REQUEST
    confirmation_id: str
    command: str
    description: Optional[str] = None


class BashConfirmationResponseMessage(BaseWebSocketMessage):
    """Bash command confirmation response message schema"""
    type: MessageType = MessageType.BASH_CONFIRMATION_RESPONSE
    confirmation_id: str
    approved: bool
    user_message: Optional[str] = None


class TitleUpdateMessage(BaseWebSocketMessage):
    """Title update message schema for session title changes"""
    type: MessageType = MessageType.TITLE_UPDATE
    payload: Dict[str, Any]  # Contains session_id and title


# Message type to schema mapping
MESSAGE_SCHEMAS = {
    MessageType.HEARTBEAT: HeartbeatMessage,
    MessageType.HEARTBEAT_ACK: HeartbeatMessage,
    MessageType.LOCATION_REQUEST: LocationRequestMessage,
    MessageType.LOCATION_RESPONSE: LocationResponseMessage,
    MessageType.CHAT_MESSAGE: ChatMessageRequest,
    MessageType.CHAT_STREAM_CHUNK: ChatStreamChunk,
    MessageType.NAGISA_IS_USING_TOOL: ToolUseNotification,
    MessageType.NAGISA_TOOL_USE_CONCLUDED: ToolUseNotification,
    MessageType.ERROR: ErrorMessage,
    MessageType.STATUS_UPDATE: StatusUpdate,
    MessageType.TTS_CHUNK: TTSChunk,
    MessageType.MESSAGE_CREATE: MessageCreateMessage,
    MessageType.EMOTION_KEYWORD: EmotionKeywordMessage,
    MessageType.TITLE_UPDATE: TitleUpdateMessage,
    MessageType.BASH_CONFIRMATION_REQUEST: BashConfirmationRequestMessage,
    MessageType.BASH_CONFIRMATION_RESPONSE: BashConfirmationResponseMessage,
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
    schema_class = MESSAGE_SCHEMAS.get(message_type, BaseWebSocketMessage)
    return schema_class(type=message_type, **kwargs)


def parse_message(data: Union[str, Dict[str, Any]]) -> BaseWebSocketMessage:
    """
    Parse incoming message data into typed message object.
    
    Args:
        data: Raw message data (JSON string or dict)
        
    Returns:
        BaseWebSocketMessage: Parsed message instance
        
    Raises:
        ValueError: If message format is invalid
    """
    if isinstance(data, str):
        import json
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON message: {data}")
    
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("Message must contain 'type' field")
    
    try:
        message_type = MessageType(data["type"])
    except ValueError:
        raise ValueError(f"Unknown message type: {data['type']}")
    
    schema_class = MESSAGE_SCHEMAS.get(message_type, BaseWebSocketMessage)
    
    try:
        return schema_class(**data)
    except Exception as e:
        raise ValueError(f"Invalid message format for type {message_type}: {e}")


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


def create_bash_confirmation_request(
    confirmation_id: str,
    command: str,
    description: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create Bash command confirmation request message

    Args:
        confirmation_id: Unique ID for confirmation request
        command: Bash command to execute
        description: Command description (optional)
        session_id: Session ID

    Returns:
        Bash confirmation request message dictionary
    """
    msg = BashConfirmationRequestMessage(
        type=MessageType.BASH_CONFIRMATION_REQUEST,
        confirmation_id=confirmation_id,
        command=command,
        description=description,
        session_id=session_id
    )
    return msg.model_dump(mode="json", exclude_none=True)