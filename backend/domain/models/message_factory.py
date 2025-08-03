"""
消息工厂

提供消息对象的创建和转换逻辑。
包含消息的业务规则和处理逻辑。
"""

from typing import Dict, Any, List
from .messages import BaseMessage, UserMessage, AssistantMessage, ImageMessage
from backend.shared.utils.text_clean import extract_response_without_think


def message_factory(data: dict) -> BaseMessage:
    """
    根据输入字典自动实例化正确的消息类型。
    
    这是领域服务，负责根据数据创建适当的消息实体。
    简化版本 - 工具调用在LLM客户端内部处理，消息存储只需要用户、助手、图片三种类型。
    
    Args:
        data: 消息数据字典
        
    Returns:
        BaseMessage: 对应类型的消息对象
        
    Raises:
        ValueError: 当图片消息缺少必要字段时
    """
    role = data.get('role')
    
    # 处理图片消息
    if role == 'image':
        if 'image_path' not in data:
            raise ValueError("Image message must have an image_path")
        return ImageMessage(
            content=data.get('content', ''),
            image_path=data['image_path'],
            id=data.get('id'),
            timestamp=data.get('timestamp')
        )
    
    # 处理普通消息
    filtered_data = {k: v for k, v in data.items() if k != 'role'}
    
    if role == 'assistant':
        return AssistantMessage(**filtered_data)
    else:
        # 用户消息或默认情况
        return UserMessage(**filtered_data)


def message_factory_no_thinking(data: dict) -> BaseMessage:
    """
    创建用于历史记录的消息对象，过滤掉 thinking 和 redacted_thinking 块。
    
    这个函数主要用于构造发送给 LLM 的历史消息，以减少不必要的 token 消耗。
    这是领域服务，处理消息内容的业务规则。

    Args:
        data: 消息数据字典
        
    Returns:
        BaseMessage: 过滤后的消息对象
    """
    role = data.get('role')
    
    # 图片消息保持不变
    if role == 'image':
        return message_factory(data)
    
    # 处理需要过滤thinking的消息
    filtered_data = {k: v for k, v in data.items() if k != 'role'}
    
    # 处理结构化内容
    if isinstance(data.get('content'), list):
        filtered_content = _filter_thinking_blocks(data['content'])
        filtered_data['content'] = filtered_content
    # 处理字符串内容
    elif isinstance(filtered_data.get('content'), str):
        filtered_data['content'] = extract_response_without_think(filtered_data['content'])
    
    # 创建消息对象
    if role == 'assistant':
        return AssistantMessage(**filtered_data)
    else:
        return UserMessage(**filtered_data)


def _filter_thinking_blocks(content_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    过滤掉thinking和redacted_thinking块。
    
    这是内部的业务逻辑，处理消息内容的特殊格式。
    
    Args:
        content_list: 消息内容列表
        
    Returns:
        List: 过滤后的内容列表
    """
    filtered_content = []
    for item in content_list:
        if isinstance(item, dict):
            if item.get('type') not in ['thinking', 'redacted_thinking']:
                filtered_content.append(item)
        else:
            filtered_content.append(item)
    
    # 如果过滤后没有内容，添加一个空的文本块
    if not filtered_content:
        filtered_content = [{"type": "text", "text": ""}]
    
    return filtered_content