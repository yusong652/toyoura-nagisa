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
    
    # Tool integration
    TOOL_CALL_REQUEST = "TOOL_CALL_REQUEST"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"
    
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


class ChatStreamChunk(BaseWebSocketMessage):
    """Chat stream chunk message schema"""
    type: MessageType = MessageType.CHAT_STREAM_CHUNK
    content: str
    chunk_type: str = "text"  # text, tool_call, status, etc.
    is_final: bool = False


class ToolCallRequest(BaseWebSocketMessage):
    """Tool call request message schema"""
    type: MessageType = MessageType.TOOL_CALL_REQUEST
    tool_name: str
    parameters: Dict[str, Any]
    request_id: str


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


# Message type to schema mapping
MESSAGE_SCHEMAS = {
    MessageType.HEARTBEAT: HeartbeatMessage,
    MessageType.HEARTBEAT_ACK: HeartbeatMessage,
    MessageType.LOCATION_REQUEST: LocationRequestMessage,
    MessageType.LOCATION_RESPONSE: LocationResponseMessage,
    MessageType.CHAT_MESSAGE: ChatMessageRequest,
    MessageType.CHAT_STREAM_CHUNK: ChatStreamChunk,
    MessageType.TOOL_CALL_REQUEST: ToolCallRequest,
    MessageType.NAGISA_IS_USING_TOOL: ToolUseNotification,
    MessageType.NAGISA_TOOL_USE_CONCLUDED: ToolUseNotification,
    MessageType.ERROR: ErrorMessage,
    MessageType.STATUS_UPDATE: StatusUpdate,
    MessageType.TTS_CHUNK: TTSChunk,
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