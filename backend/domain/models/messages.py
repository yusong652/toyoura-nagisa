"""
消息领域模型

定义聊天应用中的核心消息实体，包括用户消息、助手消息和图片消息。
这些是纯粹的领域对象，不包含任何基础设施或表示层的依赖。
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union, Literal
from datetime import datetime


# =====================
# 消息模型基类
# =====================
class BaseMessage(BaseModel):
    """
    所有消息类型的基类。
    
    这是领域层的核心实体，表示聊天中的基本消息概念。
    """
    content: Union[str, List[dict]]
    id: Optional[str] = None
    timestamp: Optional[datetime] = None


# =====================
# 具体消息类型
# =====================
class UserMessage(BaseMessage):
    """
    用户的普通文本消息。
    
    表示来自用户的输入消息，是聊天对话的一方。
    """
    role: Literal["user"] = "user"


class AssistantMessage(BaseMessage):
    """
    助手的普通文本消息。
    
    表示AI助手的回复消息，是聊天对话的另一方。
    """
    role: Literal["assistant"] = "assistant"


class ImageMessage(BaseModel):
    """
    生成的图片消息。
    
    表示系统生成或处理的图片内容，包含图片路径信息。
    """
    content: Union[str, List[dict]]
    id: Optional[str] = None
    timestamp: Optional[datetime] = None
    image_path: str
    role: Literal["image"] = "image"


# =====================
# 类型定义
# =====================
MessageType = Union[UserMessage, AssistantMessage, ImageMessage]
Message = MessageType  # 兼容原有类型提示