from pydantic import BaseModel, Field # 导入 Pydantic 的 BaseModel 和 Field
from typing import List, Optional, Literal, Union # 导入类型提示和 Literal 以及 Union
from datetime import datetime # 导入 datetime 模块

# 定义单条消息的结构 (可选，但对于管理历史记录很有用)
class Message(BaseModel):
    role: Literal['user', 'assistant', 'system'] = Field(..., description="消息发送者角色")
    content: Union[str, List[dict]] = Field(..., description="消息内容，可以是字符串或多模态内容列表")
    timestamp: Optional[datetime] = Field(None, description="消息时间戳（可选）")

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