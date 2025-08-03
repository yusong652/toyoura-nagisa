"""
API 请求和响应模型

定义Web API的数据传输对象（DTOs），包括请求和响应的结构。
这些模型专门用于HTTP API层，与领域模型分离。
"""

from pydantic import BaseModel, Field
from typing import Optional


# =====================
# 基础响应模型
# =====================
class ErrorResponse(BaseModel):
    """API错误响应模型"""
    detail: str = Field(..., description="错误信息")


# =====================
# 会话管理相关模型
# =====================
class NewHistoryRequest(BaseModel):
    """创建新历史记录的请求模型"""
    name: Optional[str] = None


class HistorySessionResponse(BaseModel):
    """历史会话响应模型"""
    id: str
    name: str
    created_at: str
    updated_at: str


class SwitchSessionRequest(BaseModel):
    """切换会话的请求模型"""
    session_id: str


class DeleteSessionRequest(BaseModel):
    """删除会话的请求模型"""
    session_id: str


# =====================
# 消息管理相关模型
# =====================
class DeleteMessageRequest(BaseModel):
    """删除消息的请求模型"""
    session_id: str
    message_id: str


# =====================
# 标题生成相关模型
# =====================
class GenerateTitleRequest(BaseModel):
    """生成标题的请求模型"""
    session_id: str


# =====================
# 功能开关相关模型
# =====================
class UpdateToolsEnabledRequest(BaseModel):
    """更新工具启用状态的请求模型"""
    enabled: bool


class UpdateTTSEnabledRequest(BaseModel):
    """更新TTS启用状态的请求模型"""
    enabled: bool


# =====================
# 图片生成相关模型
# =====================
class GenerateImageRequest(BaseModel):
    """一键生成图片的请求模型"""
    session_id: str