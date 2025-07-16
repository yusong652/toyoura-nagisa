from pydantic import BaseModel, Field # 导入 Pydantic 的 BaseModel 和 Field
from typing import List, Optional, Dict, Any, Union, Literal # 导入类型提示和 Literal 以及 Union
from datetime import datetime # 导入 datetime 模块
import json
from backend.utils.text_clean import extract_response_without_think

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

# =====================
# 纯文本用户消息
# =====================
class UserMessage(BaseMessage):
    """
    用户的普通文本消息。
    """
    role: Literal["user"] = "user"

# =====================
# 纯文本助手消息
# =====================
class AssistantMessage(BaseMessage):
    """
    助手的普通文本消息。
    """
    role: Literal["assistant"] = "assistant"

# =====================
# 工具调用消息（助手发起）
# =====================
class AssistantToolMessage(BaseMessage):
    """
    LLM 触发的工具调用消息（function call），等待工具执行并返回结果。
    """
    tool_calls: List[Dict[str, Any]]
    content: Optional[Union[str, List[dict]]] = None  # 使 content 成为可选字段
    role: Literal["assistant"] = "assistant"

# =====================
# 工具调用结果消息（工具响应，回复 AssistantToolMessage）
# =====================
class ToolResultMessage(BaseMessage):
    """
    工具调用的结果消息（tool result），用于回复 AssistantToolMessage。
    这是工具执行后返回的结果消息。
    """
    tool_call_id: str  # 确保这是必需的字段
    name: str
    content: Any  # 使用 Any 类型，因为工具返回的内容可能是任何类型
    role: Literal["tool"] = "tool"

# =====================
# 图片消息
# =====================
class ImageMessage(BaseModel):
    """
    生成的图片消息。
    """
    content: Union[str, List[dict]]
    id: Optional[str] = None
    timestamp: Optional[datetime] = None
    image_path: str
    role: Literal["image"] = "image"

# =====================
# 类型提示用 Union
# =====================
MessageType = Union[UserMessage, AssistantMessage, AssistantToolMessage, ToolResultMessage, ImageMessage]

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
        return ToolResultMessage(
            tool_call_id=data['tool_call_id'],
            name=data['name'],
            content=data['content']
        )
    elif data.get('role') == 'image':
        if 'image_path' not in data:
            raise ValueError("Image message must have an image_path")
        return ImageMessage(
            content=data.get('content', ''),
            image_path=data['image_path'],
            id=data.get('id'),
            timestamp=data.get('timestamp')
        )
    elif 'tool_calls' in data:
        # AssistantToolMessage 也需要过滤 content
        filtered_data = {k: v for k, v in data.items() if k != 'role'}
        if 'content' in filtered_data and isinstance(filtered_data['content'], str):
            filtered_data['content'] = extract_response_without_think(filtered_data['content'])
        return AssistantToolMessage(**filtered_data)
    
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
        filtered_data = {k: v for k, v in data.items() if k != 'role'}
        if 'content' in filtered_data and isinstance(filtered_data['content'], str):
            filtered_data['content'] = extract_response_without_think(filtered_data['content'])
        return AssistantMessage(**filtered_data)
    elif role == 'user':
        return UserMessage(**{k: v for k, v in data.items() if k != 'role'})
    else:
        # If no role is specified, try to infer from content
        if isinstance(data.get('content'), str) and data.get('content', '').startswith('[[thinking]]'):
            return AssistantMessage(**{k: v for k, v in data.items() if k != 'role'})
        else:
            return UserMessage(**{k: v for k, v in data.items() if k != 'role'})

# =====================
# 创建历史记录消息
# =====================
def message_factory_no_thinking(data: dict) -> BaseMessage:
    """
    message_factory_no_thinking: 创建用于历史记录的消息对象，过滤掉 thinking 和 redacted_thinking 块。
    这个函数主要用于构造发送给 LLM 的历史消息，以减少不必要的 token 消耗。
    
    Args:
        data: 消息数据字典
        
    Returns:
        BaseMessage: 过滤后的消息对象
    """
    # 首先处理工具相关的消息，这些保持不变
    if data.get('role') == 'tool':
        if 'tool_call_id' not in data:
            raise ValueError("Tool response message must have a tool_call_id")
        return ToolResultMessage(
            tool_call_id=data['tool_call_id'],
            name=data['name'],
            content=data['content']
        )
    elif data.get('role') == 'image':
        if 'image_path' not in data:
            raise ValueError("Image message must have an image_path")
        return ImageMessage(
            content=data.get('content', ''),
            image_path=data['image_path'],
            id=data.get('id'),
            timestamp=data.get('timestamp')
        )
    elif 'tool_calls' in data:
        filtered_data = {k: v for k, v in data.items() if k != 'role'}
        if 'content' in filtered_data and isinstance(filtered_data['content'], str):
            filtered_data['content'] = extract_response_without_think(filtered_data['content'])
        return AssistantToolMessage(**filtered_data)
    
    # 处理带有结构化内容的消息
    if isinstance(data.get('content'), list):
        # 过滤掉 thinking 和 redacted_thinking 块，只保留 text 和其他类型的块
        filtered_content = []
        for item in data['content']:
            if isinstance(item, dict):
                if item.get('type') not in ['thinking', 'redacted_thinking']:
                    filtered_content.append(item)
            else:
                filtered_content.append(item)
        
        # 如果过滤后没有内容，添加一个空的文本块
        if not filtered_content:
            filtered_content = [{"type": "text", "text": ""}]
        
        # 更新消息数据
        filtered_data = {k: v for k, v in data.items() if k != 'role'}
        filtered_data['content'] = filtered_content
        
        if data.get('role') == 'assistant':
            return AssistantMessage(**filtered_data)
        else:
            return UserMessage(**filtered_data)
    
    # 处理字符串内容的消息
    role = data.get('role')
    filtered_data = {k: v for k, v in data.items() if k != 'role'}
    if role == 'assistant':
        if isinstance(filtered_data.get('content'), str):
            filtered_data['content'] = extract_response_without_think(filtered_data['content'])
        return AssistantMessage(**filtered_data)
    else:
        return UserMessage(**filtered_data)

# =====================
# 兼容原有类型提示
# =====================
# Message 只做类型提示，不可实例化
Message = MessageType

# =====================
# 简化的响应模型 - SOTA版本
# =====================
class ErrorResponse(BaseModel):
    detail: str = Field(..., description="错误信息")

class LLMResponse:
    """
    简化的LLM响应类 - 专为新架构设计
    
    由于工具调用现在在LLM客户端内部处理，这个类只需要处理最终的文本响应。
    移除了所有过时的工具调用相关字段和ResponseType依赖。
    """
    def __init__(
        self,
        content: Union[str, List[Dict[str, Any]]],
        keyword: Optional[str] = None,
        error: Optional[str] = None,
    ):
        # 确保 content 总是列表格式
        if isinstance(content, str):
            if error:
                # 错误情况下，content可能是错误信息字符串
                self.content = [{"type": "text", "text": content}]
                self.is_error = True
            else:
                self.content = [{"type": "text", "text": content}]
                self.is_error = False
        else:
            self.content = content
            self.is_error = bool(error)
        
        self.keyword = keyword
        self.error = error

    def to_dict(self) -> dict:
        """
        将 LLMResponse 转换为字典格式。
        """
        result = {
            "content": self.content,
            "keyword": self.keyword,
        }
        if self.is_error:
            result["error"] = self.error
        return result

# =====================
# API 请求和响应模型
# =====================

# 历史记录相关模型
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

class DeleteMessageRequest(BaseModel):
    """删除消息的请求模型"""
    session_id: str
    message_id: str

# 标题生成相关模型
class GenerateTitleRequest(BaseModel):
    """生成标题的请求模型"""
    session_id: str

# 功能开关相关模型
class UpdateToolsEnabledRequest(BaseModel):
    """更新工具启用状态的请求模型"""
    enabled: bool

class UpdateTTSEnabledRequest(BaseModel):
    """更新TTS启用状态的请求模型"""
    enabled: bool

# 图片生成相关模型
class GenerateImageRequest(BaseModel):
    """一键生成图片的请求模型"""
    session_id: str