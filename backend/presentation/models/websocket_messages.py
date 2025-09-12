"""WebSocket消息模型定义 - 确保前后端消息类型一致性"""

from typing import Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """WebSocket消息类型枚举"""
    # 系统消息
    CONNECTION_ESTABLISHED = "CONNECTION_ESTABLISHED"
    CONNECTION_CLOSED = "CONNECTION_CLOSED"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    ERROR = "error"
    
    # 聊天消息
    CHAT_MESSAGE = "CHAT_MESSAGE"
    CHAT_RESPONSE = "CHAT_RESPONSE"
    STATUS_UPDATE = "STATUS_UPDATE"
    
    # 工具相关
    NAGISA_IS_USING_TOOL = "NAGISA_IS_USING_TOOL"
    NAGISA_TOOL_USE_CONCLUDED = "NAGISA_TOOL_USE_CONCLUDED"
    
    # 标题更新
    TITLE_UPDATE = "TITLE_UPDATE"
    
    # 位置相关
    REQUEST_LOCATION = "REQUEST_LOCATION"
    LOCATION_RESPONSE = "LOCATION_RESPONSE"
    
    # TTS相关
    TTS_CHUNK = "TTS_CHUNK"
    TTS_COMPLETE = "TTS_COMPLETE"
    
    # Bash命令确认相关
    BASH_CONFIRMATION_REQUEST = "BASH_CONFIRMATION_REQUEST"
    BASH_CONFIRMATION_RESPONSE = "BASH_CONFIRMATION_RESPONSE"


class BaseWebSocketMessage(BaseModel):
    """WebSocket消息基类"""
    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)


class ConnectionMessage(BaseWebSocketMessage):
    """连接相关消息"""
    type: Literal[MessageType.CONNECTION_ESTABLISHED, MessageType.CONNECTION_CLOSED]
    code: Optional[int] = None
    reason: Optional[str] = None


class HeartbeatMessage(BaseWebSocketMessage):
    """心跳消息"""
    type: Literal[MessageType.HEARTBEAT, MessageType.HEARTBEAT_ACK]


class ErrorMessage(BaseWebSocketMessage):
    """错误消息"""
    type: Literal[MessageType.ERROR]
    error: str
    details: Optional[Dict[str, Any]] = None
    recoverable: bool = True


class StatusMessage(BaseWebSocketMessage):
    """状态更新消息"""
    type: Literal[MessageType.STATUS_UPDATE]
    status: Literal["sent", "read", "typing", "thinking", "complete", "retrieving_memories", "memory_injected", "memory_injection_skipped", "memory_error"]
    message_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ToolUseMessage(BaseWebSocketMessage):
    """工具使用消息"""
    type: Literal[MessageType.NAGISA_IS_USING_TOOL, MessageType.NAGISA_TOOL_USE_CONCLUDED]
    tool_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class TitleUpdateMessage(BaseWebSocketMessage):
    """标题更新消息"""
    type: Literal[MessageType.TITLE_UPDATE]
    payload: Dict[str, str] = Field(description="包含session_id和title")


class LocationRequestMessage(BaseWebSocketMessage):
    """位置请求消息"""
    type: Literal[MessageType.REQUEST_LOCATION]
    reason: Optional[str] = None


class LocationResponseMessage(BaseWebSocketMessage):
    """位置响应消息"""
    type: Literal[MessageType.LOCATION_RESPONSE]
    location_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TTSMessage(BaseWebSocketMessage):
    """TTS消息"""
    type: Literal[MessageType.TTS_CHUNK, MessageType.TTS_COMPLETE]
    audio_url: Optional[str] = None
    text: Optional[str] = None
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None


class BashConfirmationRequestMessage(BaseWebSocketMessage):
    """Bash命令确认请求消息"""
    type: Literal[MessageType.BASH_CONFIRMATION_REQUEST]
    confirmation_id: str
    command: str
    description: Optional[str] = None


class BashConfirmationResponseMessage(BaseWebSocketMessage):
    """Bash命令确认响应消息"""
    type: Literal[MessageType.BASH_CONFIRMATION_RESPONSE]
    confirmation_id: str
    approved: bool


class ChatMessage(BaseWebSocketMessage):
    """聊天消息"""
    type: Literal[MessageType.CHAT_MESSAGE, MessageType.CHAT_RESPONSE]
    content: Union[str, Dict[str, Any], list]
    message_id: str
    role: Literal["user", "assistant", "system"]
    keyword: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# 消息类型映射
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
    """验证并解析WebSocket消息
    
    Args:
        data: 原始消息数据
        
    Returns:
        验证后的消息对象
        
    Raises:
        ValueError: 如果消息格式无效
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
    """创建错误消息
    
    Args:
        error: 错误描述
        session_id: 会话ID
        details: 额外的错误详情
        recoverable: 是否可恢复
        
    Returns:
        错误消息字典
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
    status: str,
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """创建状态消息
    
    Args:
        status: 状态值
        session_id: 会话ID
        message_id: 消息ID
        details: 额外的状态详情
        
    Returns:
        状态消息字典
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
    """创建工具使用消息
    
    Args:
        is_using: 是否正在使用工具
        tool_name: 工具名称
        parameters: 工具参数
        action: 动作描述
        result: 工具结果
        session_id: 会话ID
        
    Returns:
        工具使用消息字典
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
    """创建Bash命令确认请求消息
    
    Args:
        confirmation_id: 确认请求的唯一ID
        command: 待执行的bash命令
        description: 命令描述（可选）
        session_id: 会话ID
        
    Returns:
        Bash确认请求消息字典
    """
    msg = BashConfirmationRequestMessage(
        type=MessageType.BASH_CONFIRMATION_REQUEST,
        confirmation_id=confirmation_id,
        command=command,
        description=description,
        session_id=session_id
    )
    return msg.model_dump(mode="json", exclude_none=True)