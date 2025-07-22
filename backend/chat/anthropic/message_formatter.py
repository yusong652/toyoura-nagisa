"""
Message formatting utilities for Anthropic Claude API.

Handles conversion between internal message formats and Anthropic API compatible formats,
including multimodal content processing and role mapping.
"""

import base64
import json
from typing import List, Dict, Any, Optional

from backend.chat.models import BaseMessage


class MessageFormatter:
    """
    Handles message formatting for Anthropic Claude API interactions.
    
    This class provides methods for:
    - Converting history messages to Anthropic API format
    - Processing multimodal content (images, documents) in user messages
    - Role mapping between formats
    
    Optimized for historical message processing only - working context
    is handled directly in context manager without formatting.
    """

    @staticmethod
    def map_role(role: str) -> str:
        """
        Map internal role names to Anthropic API role names.
        
        Args:
            role: Internal role name
            
        Returns:
            Anthropic API compatible role name
        """
        # Anthropic uses "user" and "assistant" directly
        if role == "model":
            return "assistant"
        return role

    @staticmethod
    def process_inline_data(inline_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process inline_data, converting base64 strings to Anthropic API format.
        
        Args:
            inline_data: Dictionary containing mime_type and data
            
        Returns:
            Anthropic API compatible image block, or None if processing fails
        """
        try:
            data_field = inline_data['data']
            mime_type = inline_data.get('mime_type', 'image/png')
            
            # If data is a string (base64), keep as is for Anthropic
            if isinstance(data_field, str):
                base64_data = data_field
            elif isinstance(data_field, bytes):
                # Convert bytes to base64 string
                base64_data = base64.b64encode(data_field).decode('utf-8')
            else:
                print(f"[WARNING] Invalid data format: expected str or bytes, got {type(data_field)}")
                return None
            
            # Return Anthropic API image block format
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64_data
                }
            }
            
        except Exception as e:
            print(f"[WARNING] Failed to process inline_data: {e}")
            return None

    @staticmethod
    def format_messages_for_anthropic(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Format history messages for Anthropic Claude API.
        
        Converts internal message format to Anthropic API compatible format:
        - User messages (text + optional multimodal content)  
        - Assistant final responses (text only)
        
        Args:
            messages: List of BaseMessage objects from conversation history
            
        Returns:
            List of formatted message dictionaries for Anthropic API
        """
        formatted_messages = []
        
        for msg in messages:
            content = []
            
            # Handle message content based on format
            if isinstance(msg.content, list):
                # Multi-part message (text + optional multimodal content)
                for item in msg.content:
                    if "text" in item and item["text"]:
                        content.append({
                            "type": "text",
                            "text": item["text"]
                        })
                    elif "inline_data" in item:
                        # Process image content
                        image_block = MessageFormatter.process_inline_data(item['inline_data'])
                        if image_block:
                            content.append(image_block)
            else:
                # Simple text message
                content.append({
                    "type": "text", 
                    "text": str(msg.content)
                })
            
            # Map role and add to messages
            mapped_role = MessageFormatter.map_role(msg.role)
            formatted_messages.append({
                "role": mapped_role,
                "content": content
            })
        
        return formatted_messages

    @staticmethod
    def format_tool_result_for_anthropic(tool_call_id: str, result: Any, is_error: bool = False) -> Dict[str, Any]:
        """
        Format tool execution result for Anthropic API.
        
        Args:
            tool_call_id: ID of the tool call
            result: Tool execution result
            is_error: Whether the result represents an error
            
        Returns:
            Anthropic API compatible tool result message
        """
        if is_error:
            content = f"Error: {str(result)}"
            is_error_flag = True
        else:
            # Convert result to string if it's not already
            if isinstance(result, (dict, list)):
                content = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                content = str(result)
            is_error_flag = False
            
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": content,
                "is_error": is_error_flag
            }]
        }