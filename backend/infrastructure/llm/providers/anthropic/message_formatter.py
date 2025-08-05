"""
Message formatting utilities for Anthropic Claude API.

Handles conversion between internal message formats and Anthropic API compatible formats,
including multimodal content processing and role mapping.
"""

import base64
from typing import List, Dict, Any, Optional, Union

from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class MessageFormatter(BaseMessageFormatter):
    """
    Handles message formatting for Anthropic Claude API interactions.
    
    This class provides methods for:
    - Converting history messages to Anthropic API format
    - Processing multimodal content (images, documents) in user messages
    - Role mapping between formats
    - Formatting tool result content for API compatibility
    
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
            # Use base class validation
            if not MessageFormatter.validate_inline_data(inline_data):
                print(f"[WARNING] inline_data missing or empty data field")
                return None
                
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
    def format_tool_result_content(result: Union[Dict[str, Any], Any]) -> Union[str, List[Dict[str, Any]]]:
        """
        Format tool result content for Anthropic API compatibility.
        
        Transforms tool execution results into Anthropic API compatible format.
        Extracts llm_content from standardized ToolResult objects and formats
        according to Anthropic's content requirements.
        
        Args:
            result: Tool execution result, typically ToolResult.model_dump() containing:
                - llm_content: Structured data for LLM consumption
                - status: Operation outcome ("success" | "error")  
                - message: User-facing summary
                Or raw content for legacy compatibility
        
        Returns:
            Union[str, List[Dict[str, Any]]]: Formatted content for Anthropic API:
                - str: JSON serialized structured data or simple text
                - List[Dict]: Multimodal content array with text and image blocks
        
        Example:
            # ToolResult with text content
            result = {"status": "success", "llm_content": {"data": "result"}}
            # Returns: '{"data": "result"}'
            
            # Result with image content  
            result = {"text": "chart", "inline_data": {"data": "base64..."}}
            # Returns: [{"type": "text", "text": '{"text": "chart"}'}, {"type": "image", ...}]
        """
        # Handle multimodal content with images (only if inline_data has actual data)
        if isinstance(result, dict) and 'inline_data' in result and result['inline_data']:
            return MessageFormatter._format_multimodal_content(result)
        
        # Handle standardized ToolResult - extract llm_content
        if isinstance(result, dict) and 'llm_content' in result:
            content = result['llm_content']
            if isinstance(content, (dict, list)):
                return MessageFormatter.safe_json_serialize(content, ensure_ascii=False, indent=2)
            return str(content)
            
        # Handle regular structured data
        if isinstance(result, (dict, list)):
            return MessageFormatter.safe_json_serialize(result, ensure_ascii=False, indent=2)
            
        # Handle simple content
        return str(result)
    
    @staticmethod
    def _format_multimodal_content(content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format content containing inline_data for multimodal display.
        
        Args:
            content: Dictionary containing inline_data with image information
            
        Returns:
            List[Dict[str, Any]]: Multimodal content array with text and image blocks
        """
        inline_data = content['inline_data']
        content_parts = []
        
        # Add text content from llm_content field
        content_parts.append({
            "type": "text",
            "text": MessageFormatter.safe_json_serialize(content['llm_content'], ensure_ascii=False)
        })
        
        # Add image content
        if inline_data['data']:
            content_parts.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": inline_data.get('mime_type', 'image/png'),
                    "data": inline_data['data']
                }
            })
        
        return content_parts

    @staticmethod
    def format_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Format history messages for Anthropic Claude API.
        
        Converts internal message format to Anthropic API compatible format:
        - User messages (text + optional multimodal content)  
        - Assistant final responses (text only)
        
        Note: Tool results are handled separately via add_tool_result pathway.
        
        Args:
            messages: List of BaseMessage objects from conversation history
            
        Returns:
            List of formatted message dictionaries for Anthropic API
        """
        formatted_messages = []
        
        for msg in messages:
            # 处理普通消息
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
    def format_tool_result_for_context(tool_call_id: str, tool_name: str, result: Any) -> Dict[str, Any]:
        """
        Format tool result for Anthropic working context.
        
        Creates complete working context entry with proper tool_result block
        formatting for Anthropic API.
        
        Args:
            tool_call_id: Tool call unique identifier
            tool_name: Name of the tool that was executed  
            result: Tool execution result (can contain inline_data for multimodal)
            
        Returns:
            Dict[str, Any]: Complete working context entry for Anthropic API
        """
        # Build tool_result block
        tool_result_block = {
            "type": "tool_result",
            "tool_use_id": tool_call_id,
            "content": MessageFormatter.format_tool_result_content(result)
        }
        
        # Build user message containing tool_result
        return {
            "role": "user",
            "content": [tool_result_block]
        }

