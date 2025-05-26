from pydantic import BaseModel, Field # 导入 Pydantic 的 BaseModel 和 Field
from typing import List, Optional, Literal, Union, Dict, Any # 导入类型提示和 Literal 以及 Union
from datetime import datetime # 导入 datetime 模块
from enum import Enum

# 定义单条消息的结构 (可选，但对于管理历史记录很有用)
class Message(BaseModel):
    role: Literal['user', 'assistant', 'system', 'tool'] = Field(..., description="消息发送者角色，兼容OpenAI function call，包括'tool'")
    content: Union[str, List[dict]] = Field(..., description="消息内容，可以是字符串或多模态内容列表")
    timestamp: Optional[datetime] = Field(None, description="消息时间戳（可选）")
    id: Optional[str] = Field(None, description="消息唯一ID（可选）")
    tool_call_id: Optional[str] = Field(None, description="工具调用唯一ID，仅role为tool时使用")
    tool_calls: Optional[List[dict]] = Field(None, description="OpenAI function call专用，assistant消息携带的tool_calls")

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