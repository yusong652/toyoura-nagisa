"""
Agent Profile API Models - Agent身份切换相关的数据模型

支持用户在编程助手、生活助手和通用助手之间切换，优化工具加载和token使用。
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class AgentProfileType(str, Enum):
    """Agent身份类型枚举"""
    CODING = "coding"           # 编程助手
    LIFESTYLE = "lifestyle"     # 生活助手  
    GENERAL = "general"         # 通用助手
    DISABLED = "disabled"       # 禁用所有工具


class AgentProfileInfo(BaseModel):
    """Agent身份信息"""
    profile_type: AgentProfileType
    name: str
    description: str
    tool_count: int
    estimated_tokens: int
    color: str
    icon: str


class UpdateAgentProfileRequest(BaseModel):
    """更新Agent身份的请求模型"""
    profile: AgentProfileType = Field(
        ...,
        description="要切换到的Agent身份类型"
    )
    session_id: Optional[str] = Field(
        None,
        description="可选的会话ID，用于清除特定会话的工具缓存"
    )


class AgentProfileResponse(BaseModel):
    """Agent身份切换响应模型"""
    success: bool
    current_profile: AgentProfileType
    profile_info: AgentProfileInfo
    tools_enabled: bool
    message: str


class GetAgentProfilesResponse(BaseModel):
    """获取所有可用Agent身份的响应模型"""
    success: bool
    current_profile: AgentProfileType
    available_profiles: List[AgentProfileInfo]
    message: str


