from pydantic import BaseModel, Field # 导入 Pydantic 的 BaseModel 和 Field
from typing import List, Optional, Dict, Any, Union, Literal # 导入类型提示和 Literal 以及 Union
from datetime import datetime # 导入 datetime 模块
from enum import Enum
import json

# =====================
# 消息模型基类
# =====================
class BaseMessage(BaseModel):
    """
    所有消息类型的基类。
    """
    content: Union[str, List[dict]]
    id: Optional[str] = None
    timestamp: Optional[datetime] = None

    # 子类必须实现 role 属性
    @property
    def role(self) -> str:
        raise NotImplementedError

# =====================
# 纯文本用户消息
# =====================
class UserMessage(BaseMessage):
    """
    用户的普通文本消息。
    """
    @property
    def role(self):
        return 'user'

# =====================
# 纯文本助手消息
# =====================
class AssistantMessage(BaseMessage):
    """
    助手的普通文本消息。
    """
    @property
    def role(self):
        return 'assistant'

# =====================
# 工具调用消息（助手发起）
# =====================
class AssistantToolMessage(BaseMessage):
    """
    LLM 触发的工具调用消息（function call），等待工具执行并返回结果。
    """
    tool_calls: List[Dict[str, Any]]
    content: Optional[Union[str, List[dict]]] = None  # 使 content 成为可选字段
    
    @property
    def role(self):
        return 'assistant'

# =====================
# 工具调用结果消息（工具响应，回复 AssistantToolMessage）
# =====================
class UserToolMessage(BaseMessage):
    """
    工具调用的结果消息（tool result），用于回复 AssistantToolMessage。
    注意：虽然 role 是 'user'，但这不是用户输入，而是工具的响应。
    """
    tool_call_id: str  # 确保这是必需的字段
    name: str
    content: Any  # 使用 Any 类型，因为工具返回的内容可能是任何类型
    
    @property
    def role(self):
        return 'tool'

# =====================
# 类型提示用 Union
# =====================
MessageType = Union[UserMessage, AssistantMessage, AssistantToolMessage, UserToolMessage]

# =====================
# 消息工厂函数
# =====================
def message_factory(data: dict) -> BaseMessage:
    """
    根据输入字典自动实例化正确的消息类型。
    """
    # First check for tool-related messages
    if data.get('role') == 'tool':
        if 'tool_call_id' not in data:
            raise ValueError("Tool response message must have a tool_call_id")
        return UserToolMessage(
            tool_call_id=data['tool_call_id'],
            name=data['name'],
            content=data['content']
        )
    elif 'tool_calls' in data:
        return AssistantToolMessage(**{k: v for k, v in data.items() if k != 'role'})
    
    # Check for tool_use in content
    if isinstance(data.get('content'), list):
        for item in data.get('content', []):
            if isinstance(item, dict) and item.get('type') == 'tool_use':
                return AssistantToolMessage(
                    content=data['content'],
                    id=item.get('id'),
                    tool_calls=[{
                        'id': item.get('id'),
                        'type': 'function',
                        'function': {
                            'name': item.get('name'),
                            'arguments': json.dumps(item.get('input', {}))
                        }
                    }]
                )
    
    # Then check for regular messages based on role
    role = data.get('role')
    if role == 'assistant':
        return AssistantMessage(**{k: v for k, v in data.items() if k != 'role'})
    elif role == 'user':
        return UserMessage(**{k: v for k, v in data.items() if k != 'role'})
    else:
        # If no role is specified, try to infer from content
        if isinstance(data.get('content'), str) and data.get('content', '').startswith('[[thinking]]'):
            return AssistantMessage(**{k: v for k, v in data.items() if k != 'role'})
        else:
            return UserMessage(**{k: v for k, v in data.items() if k != 'role'})

# =====================
# 兼容原有类型提示
# =====================
# Message 只做类型提示，不可实例化
Message = MessageType

# =====================
# 其它模型
# =====================
class ChatRequest(BaseModel):
    messageText: str = Field(..., description="用户输入的最新消息文本")
    session_id: Optional[str] = Field(None, description="用户会话 ID")

class ChatResponse(BaseModel):
    response: str = Field(..., description="LLM 生成的回复文本")
    keyword: str = Field(..., description="情绪/动作关键词")
    audio_data: str = Field(..., description="TTS 音频的 base64 编码 mp3 数据")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="错误信息")

class ResponseType(str, Enum):
    TEXT = "text"
    FUNCTION_CALL = "function_call"
    ERROR = "error"

class LLMResponse:
    def __init__(
        self,
        content: str,
        response_type: ResponseType,
        keyword: Optional[str] = None,
        function_name: Optional[str] = None,
        function_args: Optional[Dict[str, Any]] = None,
        function_result: Optional[Any] = None,
        function_call_id: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ):
        self.content = content
        self.response_type = response_type
        self.keyword = keyword
        self.function_name = function_name
        self.function_args = function_args
        self.function_result = function_result
        self.function_call_id = function_call_id
        self.tool_calls = tool_calls or []

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "response_type": self.response_type,
            "keyword": self.keyword,
            "function_name": self.function_name,
            "function_args": self.function_args,
            "function_result": self.function_result,
            "function_call_id": self.function_call_id,
            "tool_calls": self.tool_calls,
        }