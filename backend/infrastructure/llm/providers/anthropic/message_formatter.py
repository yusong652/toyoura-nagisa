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
            result: Tool execution result with standardized parts format:
                - llm_content.parts: List of content parts (text and/or inline_data)
                - status: Operation outcome ("success" | "error")
                - message: User-facing summary

        Returns:
            Union[str, List[Dict[str, Any]]]: Formatted content for Anthropic API:
                - str: JSON serialized structured data or simple text
                - List[Dict]: Multimodal content array with text and image blocks

        Example:
            # ToolResult with text content
            result = {"status": "success", "llm_content": {"parts": [{"type": "text", "text": "result"}]}}
            # Returns: 'result'

            # Result with image content
            result = {"llm_content": {"parts": [{"type": "text", "text": "image"}, {"type": "inline_data", ...}]}}
            # Returns: [{"type": "text", "text": "image"}, {"type": "image", ...}]
        """
        # All tools use standardized parts format
        llm_content = result["llm_content"]
        content_parts = llm_content["parts"]
        formatted_parts = []

        for part in content_parts:
            part_type = part["type"]

            if part_type == "text":
                # Add text block
                text_content = part.get("text", "")
                if text_content:
                    formatted_parts.append({
                        "type": "text",
                        "text": text_content
                    })
            elif part_type == "inline_data":
                # Process inline_data and convert to Anthropic image format
                image_block = MessageFormatter.process_inline_data(part)
                if image_block:
                    formatted_parts.append(image_block)

        # Return as list for multimodal, or extract text for text-only
        if len(formatted_parts) == 1 and formatted_parts[0]["type"] == "text":
            return formatted_parts[0]["text"]

        return formatted_parts

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
                # Multi-part message (text + optional multimodal content + tool_result + tool_use)
                for item in msg.content:
                    # Handle tool_result type (from history)
                    if item.get("type") == "tool_result":
                        # Extract nested content.parts and format it
                        nested_content = item.get("content", {})
                        if isinstance(nested_content, dict) and "parts" in nested_content:
                            # Use format_tool_result_content with adapted structure
                            formatted_content = MessageFormatter.format_tool_result_content({
                                "llm_content": nested_content
                            })
                        else:
                            # Fallback: use content as-is
                            formatted_content = nested_content

                        # Build tool_result block for API
                        content.append({
                            "type": "tool_result",
                            "tool_use_id": item.get("tool_use_id", ""),
                            "content": formatted_content
                        })
                    # Handle tool_use type (from assistant history)
                    elif item.get("type") == "tool_use":
                        content.append({
                            "type": "tool_use",
                            "id": item.get("id", ""),
                            "name": item.get("name", ""),
                            "input": item.get("input", {})
                        })
                    # Handle thinking type (from assistant history)
                    elif item.get("type") == "thinking":
                        thinking_block = {"type": "thinking", "thinking": item.get("thinking", "")}
                        # Only include signature if present
                        if "signature" in item and item["signature"]:
                            thinking_block["signature"] = item["signature"]
                        content.append(thinking_block)
                    elif "text" in item and item["text"]:
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
            mapped_role = MessageFormatter.map_role(getattr(msg, 'role', 'user'))
            formatted_messages.append({
                "role": mapped_role,
                "content": content
            })
        
        return formatted_messages

    @staticmethod
    def format_single_message(message: BaseMessage) -> Dict[str, Any]:
        """
        Format a single BaseMessage to Anthropic API format.
        
        Args:
            message: Single BaseMessage to format
            
        Returns:
            Dict[str, Any]: Single message in Anthropic API format
        """
        if message is None:
            return {}
            
        content = []

        # Handle message content based on format
        if isinstance(message.content, list):
            # Multi-part message (text + optional multimodal content + tool_result + tool_use)
            for item in message.content:
                # Handle tool_result type (from history)
                if item.get("type") == "tool_result":
                    # Extract nested content.parts and format it
                    nested_content = item.get("content", {})
                    if isinstance(nested_content, dict) and "parts" in nested_content:
                        # Use format_tool_result_content with adapted structure
                        formatted_content = MessageFormatter.format_tool_result_content({
                            "llm_content": nested_content
                        })
                    else:
                        # Fallback: use content as-is
                        formatted_content = nested_content

                    # Build tool_result block for API
                    content.append({
                        "type": "tool_result",
                        "tool_use_id": item.get("tool_use_id", ""),
                        "content": formatted_content
                    })
                # Handle tool_use type (from assistant history)
                elif item.get("type") == "tool_use":
                    content.append({
                        "type": "tool_use",
                        "id": item.get("id", ""),
                        "name": item.get("name", ""),
                        "input": item.get("input", {})
                    })
                # Handle thinking type (from assistant history)
                elif item.get("type") == "thinking":
                    thinking_block = {"type": "thinking", "thinking": item.get("thinking", "")}
                    # Only include signature if present
                    if "signature" in item and item["signature"]:
                        thinking_block["signature"] = item["signature"]
                    content.append(thinking_block)
                elif "text" in item and item["text"]:
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
                "text": str(message.content)
            })
        
        # Map role and return formatted message
        if content:
            mapped_role = MessageFormatter.map_role(getattr(message, 'role', 'user'))
            return {
                "role": mapped_role,
                "content": content
            }
        
        return {}

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

