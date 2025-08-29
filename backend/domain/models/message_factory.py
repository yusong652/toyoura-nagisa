"""
Message Factory

Provides message object creation and conversion logic.
Contains business rules and processing logic for messages.
"""

from typing import Dict, Any, List
from .messages import BaseMessage, UserMessage, AssistantMessage, ImageMessage, VideoMessage
from backend.shared.utils.text_clean import extract_response_without_think


def message_factory(data: dict) -> BaseMessage:
    """
    Automatically instantiate the correct message type based on input dictionary.
    
    This is a domain service responsible for creating appropriate message entities from data.
    Simplified version - tool calls are handled internally by LLM client, 
    message storage only needs user, assistant, and image message types.
    
    Args:
        data: Message data dictionary
        
    Returns:
        BaseMessage: Corresponding message object type
        
    Raises:
        ValueError: When image message lacks required fields
    """
    role = data.get('role')
    
    # Handle image messages
    if role == 'image':
        if 'image_path' not in data:
            raise ValueError("Image message must have an image_path")
        return ImageMessage(
            content=data.get('content', ''),
            image_path=data['image_path'],
            id=data.get('id'),
            timestamp=data.get('timestamp')
        )
    
    # Handle video messages
    if role == 'video':
        if 'video_path' not in data:
            raise ValueError("Video message must have a video_path")
        return VideoMessage(
            content=data.get('content', ''),
            video_path=data['video_path'],
            id=data.get('id'),
            timestamp=data.get('timestamp')
        )
    
    # Handle regular messages
    filtered_data = {k: v for k, v in data.items() if k != 'role'}
    
    if role == 'assistant':
        return AssistantMessage(**filtered_data)
    else:
        # User message or default case
        return UserMessage(**filtered_data)


def message_factory_no_thinking(data: dict) -> BaseMessage:
    """
    Create message objects for history records, filtering out thinking and redacted_thinking blocks.
    
    This function is mainly used to construct historical messages sent to LLM,
    reducing unnecessary token consumption.
    This is a domain service that handles business rules for message content.

    Args:
        data: Message data dictionary
        
    Returns:
        BaseMessage: Filtered message object
    """
    role = data.get('role')
    
    # Image and video messages remain unchanged
    if role in ['image', 'video']:
        return message_factory(data)
    
    # Handle messages that need thinking filtering
    filtered_data = {k: v for k, v in data.items() if k != 'role'}
    
    # Handle structured content
    if isinstance(data.get('content'), list):
        filtered_content = _filter_thinking_blocks(data['content'])
        filtered_data['content'] = filtered_content
    # Handle string content
    elif isinstance(filtered_data.get('content'), str):
        filtered_data['content'] = extract_response_without_think(filtered_data['content'])
    
    # Create message object
    if role == 'assistant':
        return AssistantMessage(**filtered_data)
    else:
        return UserMessage(**filtered_data)


def extract_text_from_message(message: BaseMessage) -> str:
    """
    Extract pure text content from message object for search and memory queries.
    
    Handles multimodal message content, extracting only text parts while ignoring images and other content.
    This is a domain service that handles business logic for message content extraction.
    
    Args:
        message: Message object
        
    Returns:
        str: Extracted pure text content
    """
    content = message.content
    
    # Handle structured content (multimodal)
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return " ".join(text_parts)
    
    # Handle simple string content
    return str(content) if content else ""


def _filter_thinking_blocks(content_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out thinking and redacted_thinking blocks.
    
    This is internal business logic that handles special formats of message content.
    
    Args:
        content_list: Message content list
        
    Returns:
        List: Filtered content list
    """
    filtered_content = []
    for item in content_list:
        if isinstance(item, dict):
            if item.get('type') not in ['thinking', 'redacted_thinking']:
                filtered_content.append(item)
        else:
            filtered_content.append(item)
    
    # If no content after filtering, add an empty text block
    if not filtered_content:
        filtered_content = [{"type": "text", "text": ""}]
    
    return filtered_content