"""WebSocket message model definitions - ensuring frontend-backend message type consistency"""

from typing import Optional, Dict, Any, Literal, Union, TypeVar, Generic
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """WebSocket message type enumeration"""
    # System messages
    CONNECTION_ESTABLISHED = "CONNECTION_ESTABLISHED"
    CONNECTION_CLOSED = "CONNECTION_CLOSED"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    ERROR = "error"
    
    # Chat messages
    CHAT_MESSAGE = "CHAT_MESSAGE"
    CHAT_RESPONSE = "CHAT_RESPONSE"
    STATUS_UPDATE = "STATUS_UPDATE"
    
    # Tool-related
    NAGISA_IS_USING_TOOL = "NAGISA_IS_USING_TOOL"
    NAGISA_TOOL_USE_CONCLUDED = "NAGISA_TOOL_USE_CONCLUDED"
    
    # Title updates
    TITLE_UPDATE = "TITLE_UPDATE"
    
    # Location-related
    REQUEST_LOCATION = "REQUEST_LOCATION"
    LOCATION_RESPONSE = "LOCATION_RESPONSE"
    
    # TTS-related
    TTS_CHUNK = "TTS_CHUNK"
    TTS_COMPLETE = "TTS_COMPLETE"
    
    # Bash command confirmation-related
    BASH_CONFIRMATION_REQUEST = "BASH_CONFIRMATION_REQUEST"
    BASH_CONFIRMATION_RESPONSE = "BASH_CONFIRMATION_RESPONSE"


MessageTypeVar = TypeVar('MessageTypeVar', bound=MessageType)

class BaseWebSocketMessage(BaseModel, Generic[MessageTypeVar]):
    """Base WebSocket message class"""
    type: MessageTypeVar
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class ConnectionMessage(BaseWebSocketMessage[Literal[MessageType.CONNECTION_ESTABLISHED, MessageType.CONNECTION_CLOSED]]):
    """Connection-related messages"""
    code: Optional[int] = None
    reason: Optional[str] = None


class HeartbeatMessage(BaseWebSocketMessage[Literal[MessageType.HEARTBEAT, MessageType.HEARTBEAT_ACK]]):
    """Heartbeat messages"""
    pass


class ErrorMessage(BaseWebSocketMessage[Literal[MessageType.ERROR]]):
    """Error messages"""
    error: str
    details: Optional[Dict[str, Any]] = None
    recoverable: bool = True


class StatusMessage(BaseWebSocketMessage[Literal[MessageType.STATUS_UPDATE]]):
    """Status update messages"""
    status: Literal["sent", "read", "typing", "thinking", "complete", "retrieving_memories", "memory_injected", "memory_injection_skipped", "memory_error"]
    message_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ToolUseMessage(BaseWebSocketMessage[Literal[MessageType.NAGISA_IS_USING_TOOL, MessageType.NAGISA_TOOL_USE_CONCLUDED]]):
    """Tool use messages"""
    tool_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class TitleUpdateMessage(BaseWebSocketMessage[Literal[MessageType.TITLE_UPDATE]]):
    """Title update messages"""
    payload: Dict[str, str] = Field(description="Contains session_id and title")


class LocationRequestMessage(BaseWebSocketMessage[Literal[MessageType.REQUEST_LOCATION]]):
    """Location request messages"""
    reason: Optional[str] = None


class LocationResponseMessage(BaseWebSocketMessage[Literal[MessageType.LOCATION_RESPONSE]]):
    """Location response messages"""
    location_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TTSMessage(BaseWebSocketMessage[Literal[MessageType.TTS_CHUNK, MessageType.TTS_COMPLETE]]):
    """TTS messages"""
    audio_url: Optional[str] = None
    text: Optional[str] = None
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None


class BashConfirmationRequestMessage(BaseWebSocketMessage[Literal[MessageType.BASH_CONFIRMATION_REQUEST]]):
    """Bash command confirmation request messages"""
    confirmation_id: str
    command: str
    description: Optional[str] = None


class BashConfirmationResponseMessage(BaseWebSocketMessage[Literal[MessageType.BASH_CONFIRMATION_RESPONSE]]):
    """Bash command confirmation response messages"""
    confirmation_id: str
    approved: bool


class ChatMessage(BaseWebSocketMessage[Literal[MessageType.CHAT_MESSAGE, MessageType.CHAT_RESPONSE]]):
    """Chat messages"""
    content: Union[str, Dict[str, Any], list]
    message_id: str
    role: Literal["user", "assistant", "system"]
    keyword: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# Message type mapping
MESSAGE_TYPE_MAP = {
    MessageType.CONNECTION_ESTABLISHED: ConnectionMessage,
    MessageType.CONNECTION_CLOSED: ConnectionMessage,
    MessageType.HEARTBEAT: HeartbeatMessage,
    MessageType.HEARTBEAT_ACK: HeartbeatMessage,
    MessageType.ERROR: ErrorMessage,
    MessageType.STATUS_UPDATE: StatusMessage,
    MessageType.NAGISA_IS_USING_TOOL: ToolUseMessage,
    MessageType.NAGISA_TOOL_USE_CONCLUDED: ToolUseMessage,
    MessageType.TITLE_UPDATE: TitleUpdateMessage,
    MessageType.REQUEST_LOCATION: LocationRequestMessage,
    MessageType.LOCATION_RESPONSE: LocationResponseMessage,
    MessageType.TTS_CHUNK: TTSMessage,
    MessageType.TTS_COMPLETE: TTSMessage,
    MessageType.BASH_CONFIRMATION_REQUEST: BashConfirmationRequestMessage,
    MessageType.BASH_CONFIRMATION_RESPONSE: BashConfirmationResponseMessage,
    MessageType.CHAT_MESSAGE: ChatMessage,
    MessageType.CHAT_RESPONSE: ChatMessage,
}


def validate_websocket_message(data: Dict[str, Any]) -> BaseWebSocketMessage:
    """Validate and parse WebSocket message

    Args:
        data: Raw message data

    Returns:
        Validated message object

    Raises:
        ValueError: If message format is invalid
    """
    if "type" not in data:
        raise ValueError("Message must have a 'type' field")
    
    msg_type = data.get("type")
    
    # 尝试转换为枚举类型
    try:
        msg_type_enum = MessageType(msg_type)
    except ValueError:
        raise ValueError(f"Unknown message type: {msg_type}")
    
    # 获取对应的消息类
    message_class = MESSAGE_TYPE_MAP.get(msg_type_enum)
    if not message_class:
        raise ValueError(f"No message class for type: {msg_type}")
    
    # 验证并返回消息对象
    try:
        return message_class(**data)
    except Exception as e:
        raise ValueError(f"Invalid message format for type {msg_type}: {e}")


def create_error_message(
    error: str,
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    recoverable: bool = True
) -> Dict[str, Any]:
    """Create error message

    Args:
        error: Error description
        session_id: Session ID
        details: Additional error details
        recoverable: Whether the error is recoverable

    Returns:
        Error message dictionary
    """
    msg = ErrorMessage(
        type=MessageType.ERROR,
        error=error,
        session_id=session_id,
        details=details,
        recoverable=recoverable
    )
    return msg.model_dump(mode="json")


def create_status_message(
    status: Literal["sent", "read", "typing", "thinking", "complete", "retrieving_memories", "memory_injected", "memory_injection_skipped", "memory_error"],
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create status message

    Args:
        status: Status value
        session_id: Session ID
        message_id: Message ID
        details: Additional status details

    Returns:
        Status message dictionary
    """
    msg = StatusMessage(
        type=MessageType.STATUS_UPDATE,
        status=status,
        session_id=session_id,
        message_id=message_id,
        details=details
    )
    return msg.model_dump(mode="json")


def create_tool_use_message(
    is_using: bool,
    tool_name: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    action: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create tool use message

    Args:
        is_using: Whether currently using tool
        tool_name: Tool name
        parameters: Tool parameters
        action: Action description
        result: Tool result
        session_id: Session ID

    Returns:
        Tool use message dictionary
    """
    msg_type = MessageType.NAGISA_IS_USING_TOOL if is_using else MessageType.NAGISA_TOOL_USE_CONCLUDED
    
    msg = ToolUseMessage(
        type=msg_type,
        tool_name=tool_name,
        parameters=parameters,
        action=action,
        result=result,
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