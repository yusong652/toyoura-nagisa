"""
OpenAI Message Formatter

Handles conversion of internal message formats to OpenAI API format.
Supports multimodal content, tool calls, and message history processing.
"""

from typing import List, Dict, Any, Union, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class OpenAIMessageFormatter(BaseMessageFormatter):
    """
    Format messages for OpenAI API consumption
    
    Converts internal message objects to OpenAI API format while preserving
    all content types including text, images, tool calls, and tool results.
    """
    
    @staticmethod
    def format_messages(
        messages: List[BaseMessage], 
        preserve_thinking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Convert internal messages to OpenAI API format
        
        Args:
            messages: List of internal message objects
            preserve_thinking: Whether to preserve thinking content in context
            
        Returns:
            List of OpenAI-formatted message dictionaries
        """
        formatted_messages = []
        
        for msg in messages:
            # Handle regular messages with multimodal content
            if isinstance(msg.content, list):
                openai_content = OpenAIMessageFormatter._format_multimodal_content(
                    msg.content, preserve_thinking
                )
                formatted_messages.append({
                    "role": msg.role,
                    "content": openai_content
                })
            else:
                # Simple text content
                text_content = str(msg.content) if msg.content else ""
                formatted_messages.append({
                    "role": msg.role,
                    "content": text_content
                })
        
        return formatted_messages
    
    @staticmethod
    def format_single_message(
        message: BaseMessage, 
        preserve_thinking: bool = True
    ) -> Dict[str, Any]:
        """
        Format a single BaseMessage to OpenAI API format
        
        Args:
            message: Single internal message object
            preserve_thinking: Whether to preserve thinking content
            
        Returns:
            Dict[str, Any]: OpenAI-formatted message dictionary
        """
        if message is None:
            return {}
            
        # Handle regular messages with multimodal content
        if isinstance(message.content, list):
            openai_content = OpenAIMessageFormatter._format_multimodal_content(
                message.content, preserve_thinking
            )
            return {
                "role": message.role,
                "content": openai_content
            }
        else:
            # Simple text content
            text_content = str(message.content) if message.content else ""
            return {
                "role": message.role,
                "content": text_content
            }
    
    @staticmethod
    def _format_multimodal_content(
        content: List[Dict[str, Any]], 
        preserve_thinking: bool = True
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        Format multimodal content for OpenAI API
        
        Args:
            content: List of content blocks
            preserve_thinking: Whether to preserve thinking content
            
        Returns:
            OpenAI-formatted content - either string for text-only or array for multimodal
        """
        formatted_content = []
        has_non_text_content = False
        
        for block in content:
            if not isinstance(block, dict):
                formatted_content.append({
                    "type": "text",
                    "text": str(block)
                })
                continue
            
            # Handle text content
            if block.get("type") == "text" and block.get("text"):
                formatted_content.append({
                    "type": "text",
                    "text": block["text"]
                })
            elif "text" in block and block["text"] and "type" not in block:
                formatted_content.append({
                    "type": "text",
                    "text": block["text"]
                })
            
            # Handle image content
            elif "inline_data" in block or block.get("type") == "image":
                inline_data = block.get("inline_data", block)
                image_block = OpenAIMessageFormatter._format_image_block(inline_data)
                if image_block:
                    formatted_content.append(image_block)
                    has_non_text_content = True
            
            # Handle pre-formatted image_url content
            elif block.get("type") == "image_url":
                formatted_content.append(block)
                has_non_text_content = True
            
            # Handle thinking content
            elif block.get("type") == "thinking" and preserve_thinking:
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    formatted_content.append({
                        "type": "text", 
                        "text": f"<thinking>{thinking_text}</thinking>"
                    })
        
        # Return optimization for text-only content
        if not has_non_text_content:
            text_parts = [block.get("text", "") for block in formatted_content if block.get("type") == "text"]
            combined_text = "".join(text_parts)
            return combined_text if combined_text else ""
        
        return formatted_content
    
    @staticmethod
    def _format_image_block(inline_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Format inline_data into OpenAI image_url block.
        
        Args:
            inline_data: Dictionary containing image data and mime_type
            
        Returns:
            Optional[Dict[str, Any]]: OpenAI-formatted image_url block or None if invalid
        """
        if not inline_data or 'data' not in inline_data or not inline_data['data']:
            return None
            
        mime_type = inline_data.get('mime_type', 'image/png')
        data = inline_data['data']
        
        # Convert bytes to base64 string if needed
        if isinstance(data, bytes):
            import base64
            data = base64.b64encode(data).decode('utf-8')
        
        # Clean up base64 string
        if isinstance(data, str):
            data = data.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{data}",
                "detail": "high"
            }
        }
    
    @staticmethod
    def _format_tool_result(content: Any) -> Union[str, List[Dict[str, Any]]]:
        """
        Format tool result content for OpenAI API with proper multimodal support.
        
        Transforms tool execution results into OpenAI API compatible format.
        Extracts llm_content from standardized ToolResult objects and formats
        according to OpenAI's content requirements.
        
        Args:
            content: Tool execution result, typically ToolResult.model_dump() containing:
                - llm_content: Structured data for LLM consumption
                - status: Operation outcome ("success" | "error")
                - message: User-facing summary
                - inline_data: Optional image data for multimodal content
                Or raw content for legacy compatibility
            
        Returns:
            Union[str, List[Dict[str, Any]]]: Formatted content for OpenAI API:
                - str: JSON serialized structured data or simple text
                - List[Dict]: Multimodal content array with text and image blocks
                
        Example:
            # ToolResult with text content
            result = {"status": "success", "llm_content": {"data": "result"}}
            # Returns: '{"data": "result"}'
            
            # Result with image content
            result = {"llm_content": {"text": "chart"}, "inline_data": {"data": "base64..."}}
            # Returns: [{"type": "text", "text": '{"text": "chart"}'}, {"type": "image_url", ...}]
        """
        # Handle multimodal content
        # Check new format: inline_data inside llm_content
        if isinstance(content, dict) and 'llm_content' in content and isinstance(content['llm_content'], dict) and 'inline_data' in content['llm_content']:
            # New format: OpenAI tool messages only support text, so extract non-image content
            llm_content = content['llm_content'].copy()
            # Remove inline_data from the response
            llm_content.pop('inline_data', None)
            if llm_content:
                return OpenAIMessageFormatter.safe_json_serialize(llm_content, ensure_ascii=False, indent=2)
            return '{"status": "image processed"}'
        # Check legacy format: inline_data at root level
        elif isinstance(content, dict) and 'llm_content' in content and 'inline_data' in content:
            llm_content = content['llm_content']
            if isinstance(llm_content, (dict, list)):
                return OpenAIMessageFormatter.safe_json_serialize(llm_content, ensure_ascii=False, indent=2)
            return str(llm_content)
        
        # Handle standardized ToolResult - extract llm_content
        if isinstance(content, dict) and 'llm_content' in content:
            llm_content = content['llm_content']
            if isinstance(llm_content, (dict, list)):
                return OpenAIMessageFormatter.safe_json_serialize(llm_content, ensure_ascii=False, indent=2)
