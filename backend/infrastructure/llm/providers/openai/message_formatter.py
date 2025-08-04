"""
OpenAI Message Formatter

Handles conversion of internal message formats to OpenAI API format.
Supports multimodal content, tool calls, and message history processing.
"""

from typing import List, Dict, Any, Union
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class MessageFormatter(BaseMessageFormatter):
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
            # Handle assistant messages with tool calls
            if msg.role == "assistant" and hasattr(msg, "tool_calls") and msg.tool_calls:
                formatted_messages.append({
                    "role": "assistant",
                    "content": MessageFormatter._extract_text_content(msg.content),
                    "tool_calls": MessageFormatter._format_tool_calls(msg.tool_calls)
                })
                continue
            
            # Handle tool result messages
            if hasattr(msg, "role") and msg.role == "tool":
                formatted_messages.append({
                    "role": "tool",
                    "content": MessageFormatter._format_tool_result(msg.content),
                    "tool_call_id": getattr(msg, "tool_call_id", "")
                })
                continue
            
            # Handle regular messages with multimodal content
            if isinstance(msg.content, list):
                openai_content = MessageFormatter._format_multimodal_content(
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
    def _format_multimodal_content(
        content: List[Dict[str, Any]], 
        preserve_thinking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Format multimodal content for OpenAI API
        
        Args:
            content: List of content blocks
            preserve_thinking: Whether to preserve thinking content
            
        Returns:
            OpenAI-formatted content blocks
        """
        formatted_content = []
        
        for block in content:
            if not isinstance(block, dict):
                # Handle non-dict content
                formatted_content.append({
                    "type": "text",
                    "text": str(block)
                })
                continue
            
            # Handle text content
            if "text" in block and "type" not in block:
                formatted_content.append({
                    "type": "text",
                    "text": block["text"]
                })
            elif block.get("type") == "text":
                formatted_content.append(block)
            
            # Handle image content (inline_data format)
            elif "inline_data" in block:
                mime_type = block["inline_data"].get("mime_type", "image/png")
                data = block["inline_data"]["data"]
                formatted_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{data}"
                    }
                })
            
            # Handle image content (image_url format)
            elif block.get("type") == "image_url":
                formatted_content.append(block)
            
            # Handle thinking content
            elif block.get("type") == "thinking" and preserve_thinking:
                # Preserve model thoughts as normal text for context
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    formatted_content.append({
                        "type": "text", 
                        "text": f"<thinking>{thinking_text}</thinking>"
                    })
            
            # Handle other content types
            else:
                formatted_content.append(block)
        
        return formatted_content
    
    @staticmethod
    def _extract_text_content(content: Union[str, List[Dict[str, Any]]]) -> str:
        """
        Extract plain text from content for tool call messages
        
        Args:
            content: Message content (string or list of blocks)
            
        Returns:
            Extracted text content
        """
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if "text" in block:
                        text_parts.append(block["text"])
                    elif block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "thinking":
                        # Include thinking in text extraction for assistant messages
                        thinking_text = block.get("thinking", "")
                        if thinking_text:
                            text_parts.append(f"<thinking>{thinking_text}</thinking>")
                else:
                    text_parts.append(str(block))
            return "".join(text_parts)
        
        return str(content) if content else ""
    
    @staticmethod
    def _format_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format tool calls for OpenAI API
        
        Args:
            tool_calls: Internal tool call format
            
        Returns:
            OpenAI-formatted tool calls
        """
        formatted_calls = []
        
        for call in tool_calls:
            formatted_calls.append({
                "id": call.get("id", ""),
                "type": "function",
                "function": {
                    "name": call.get("name", ""),
                    "arguments": MessageFormatter._format_arguments(call.get("arguments", {}))
                }
            })
        
        return formatted_calls
    
    @staticmethod
    def _format_arguments(arguments: Union[Dict[str, Any], str]) -> str:
        """
        Format tool call arguments as JSON string
        
        Args:
            arguments: Tool arguments (dict or string)
            
        Returns:
            JSON-formatted arguments string
        """
        if isinstance(arguments, str):
            return arguments
        
        return MessageFormatter.safe_json_serialize(arguments, ensure_ascii=False)
    
    @staticmethod
    def _format_tool_result(content: Any) -> str:
        """
        Format tool result content for OpenAI API
        
        Args:
            content: Tool result content
            
        Returns:
            Formatted tool result string
        """
        if isinstance(content, str):
            return content
        
        return MessageFormatter.safe_json_serialize(content, ensure_ascii=False)