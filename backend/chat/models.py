from pydantic import BaseModel, Field # 导入 Pydantic 的 BaseModel 和 Field
from typing import List, Optional, Literal, Union, Dict, Any # 导入类型提示和 Literal 以及 Union
from datetime import datetime # 导入 datetime 模块
from enum import Enum

# 基础消息模型
class BaseMessage(BaseModel):
    role: Literal['user', 'assistant', 'system', 'tool']
    content: Union[str, List[dict]]
    timestamp: Optional[datetime] = None
    id: Optional[str] = None

class UserMessage(BaseMessage):
    role: Literal['user']
    # 可扩展user特有字段

class AssistantMessage(BaseMessage):
    role: Literal['assistant']
    tool_calls: Optional[List[dict]] = None
    # 只assistant有tool_calls

class ToolMessage(BaseMessage):
    role: Literal['tool']
    tool_call_id: str
    # 只tool有tool_call_id

class SystemMessage(BaseMessage):
    role: Literal['system']
    # 可扩展system特有字段

# 工厂函数
MessageType = Union[UserMessage, AssistantMessage, ToolMessage, SystemMessage]
def message_factory(data: dict) -> MessageType:
    role = data.get('role')
    if role == 'assistant':
        return AssistantMessage(**data)
    elif role == 'tool':
        return ToolMessage(**data)
    elif role == 'user':
        return UserMessage(**data)
    elif role == 'system':
        return SystemMessage(**data)
    else:
        raise ValueError(f"Unknown message role: {role}")

# 兼容原有类型
Message = BaseMessage

# 定义前端发送到 /api/chat 的请求体结构
class ChatRequest(BaseModel):
    messageText: str = Field(..., description="用户输入的最新消息文本")
    session_id: Optional[str] = Field(None, description="用户会话 ID")


# 定义 /api/chat 成功时，后端返回给前端的响应体结构
class ChatResponse(BaseModel):
    response: str = Field(..., description="LLM 生成的回复文本")
    keyword: str = Field(..., description="情绪/动作关键词")
    audio_data: str = Field(..., description="TTS 音频的 base64 编码 mp3 数据")
# (可选) 也可以定义一个错误时的响应模型
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
    ):
        self.content = content
        self.response_type = response_type
        self.keyword = keyword
        self.function_name = function_name
        self.function_args = function_args
        self.function_result = function_result
        self.function_call_id = function_call_id

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "response_type": self.response_type,
            "keyword": self.keyword,
            "function_name": self.function_name,
            "function_args": self.function_args,
            "function_result": self.function_result,
            "function_call_id": self.function_call_id,
        }