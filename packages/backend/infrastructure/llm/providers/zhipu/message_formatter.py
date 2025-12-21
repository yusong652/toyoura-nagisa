"""
Zhipu (智谱) Message Formatter

Handles conversion of internal message formats to Zhipu official API format (via zai SDK).

Although Zhipu API format is similar to OpenAI Chat Completions API, we maintain
a separate formatter to ensure:
1. Independence from OpenAI-compatible providers
2. Flexibility for Zhipu-specific API changes
3. Clear architectural separation between official SDK and compatible APIs

Supports multimodal content, tool calls, thinking content, and message history processing.
"""

import json
from typing import List, Dict, Any, Union, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class ZhipuMessageFormatter(BaseMessageFormatter):
    """
    Format messages for Zhipu official API consumption (via zai SDK)

    Converts internal message objects to Zhipu API format while preserving
    all content types including text, images, tool calls, thinking content,
    and tool results.

    This formatter is specifically designed for Zhipu's official API via zai SDK,
    ensuring independence from OpenAI-compatible providers.
    """

    @staticmethod
    def format_messages(
        messages: List[BaseMessage],
    ) -> List[Dict[str, Any]]:
        """
        Convert internal messages to Zhipu API format.

        Always preserves thinking content for cross-turn reasoning continuity.

        Args:
            messages: List of internal message objects

        Returns:
            List of Zhipu-formatted message dictionaries
        """
        formatted_messages = []

        for msg in messages:
            # format_single_message may return a dict or a list (for tool_result blocks)
            formatted = ZhipuMessageFormatter.format_single_message(msg)

            if isinstance(formatted, list):
                # Multiple messages (tool_result blocks converted to separate messages)
                formatted_messages.extend(formatted)
            elif formatted:  # Check if not empty dict
                # Single message
                formatted_messages.append(formatted)

        return formatted_messages

    @staticmethod
    def format_single_message(
        message: BaseMessage,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Format a single BaseMessage to Zhipu API format.

        Always preserves thinking content for cross-turn reasoning continuity.

        Args:
            message: Single internal message object

        Returns:
            Union[Dict[str, Any], List[Dict[str, Any]]]:
                - Single message dict for regular messages
                - List of messages for tool_result blocks (converted to role: "tool")
        """
        if message is None:
            return {}

        # Handle simple text content
        if not isinstance(message.content, list):
            return {
                "role": message.role,  # type: ignore
                "content": str(message.content) if message.content else ""
            }

        # Handle multimodal content - classify blocks by type
        thinking_text = None
        tool_use_blocks = []
        tool_result_blocks = []
        text_blocks = []
        image_blocks = []

        for block in message.content:
            if not isinstance(block, dict):
                # Non-dict blocks treated as text
                text_blocks.append({"type": "text", "text": str(block)})
                continue

            block_type = block.get("type")

            if block_type == "thinking":
                # Always preserve thinking content
                thinking_content = block.get("thinking", "")
                if thinking_content and thinking_content.strip():
                    thinking_text = thinking_content

            elif block_type == "tool_use":
                tool_use_blocks.append(block)

            elif block_type == "tool_result":
                tool_result_blocks.append(block)

            elif block_type == "text":
                text_content = block.get("text", "")
                # Only keep text if it has non-whitespace content
                if text_content and text_content.strip():
                    text_blocks.append(block)

            elif block_type == "image" or "inline_data" in block:
                # Format image block
                inline_data = block.get("inline_data", block)
                image_block = ZhipuMessageFormatter._format_image_block(inline_data)
                if image_block:
                    image_blocks.append(image_block)

            elif block_type == "image_url":
                # Pre-formatted image_url
                image_blocks.append(block)

        # Handle tool_result blocks as separate messages (role: "tool")
        if tool_result_blocks:
            tool_messages = []
            for tool_result_block in tool_result_blocks:
                tool_call_id = tool_result_block.get("tool_use_id", "")
                nested_content = tool_result_block.get("content", {})

                # Format tool result content
                if isinstance(nested_content, dict) and "parts" in nested_content:
                    formatted_content = ZhipuMessageFormatter._format_tool_result({
                        "llm_content": nested_content
                    })
                else:
                    formatted_content = nested_content

                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": formatted_content
                })
            return tool_messages if len(tool_messages) > 1 else tool_messages[0]

        # Build message result
        result: Dict[str, Any] = {"role": message.role}  # type: ignore

        # Add reasoning_content if present (separate field)
        if thinking_text is not None:
            result["reasoning_content"] = thinking_text

        # Build content field
        content_value: Union[str, List[Dict[str, Any]]]

        # Determine content format
        has_images = len(image_blocks) > 0
        has_tool_calls = len(tool_use_blocks) > 0

        if has_tool_calls or (not has_images and len(text_blocks) > 0):
            # When tool_calls present OR text-only: content must be string
            text_parts = [block.get("text", "") for block in text_blocks]
            content_value = "".join(text_parts)
        elif has_images:
            # Multimodal content: return array
            content_value = text_blocks + image_blocks
        else:
            # Empty content
            content_value = ""

        # Only add content field if it has value
        # When tool_calls present with no text, omit content field entirely
        if content_value or not has_tool_calls:
            result["content"] = content_value

        # Add tool_calls if present
        if tool_use_blocks:
            tool_calls = []
            for tool_use in tool_use_blocks:
                input_data = tool_use.get("input", {})
                arguments_str = json.dumps(input_data, ensure_ascii=False) if isinstance(input_data, dict) else str(input_data)

                tool_calls.append({
                    "id": tool_use.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tool_use.get("name", ""),
                        "arguments": arguments_str
                    }
                })
            result["tool_calls"] = tool_calls

        return result

    @staticmethod
    def _format_image_block(inline_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Format inline_data block for Zhipu API.

        GLM-4V models support image_url format with base64 data URL.
        We keep the inline_data format consistent throughout the pipeline
        and convert to image_url format here for API compatibility.

        Args:
            inline_data: Dictionary containing image data and mime_type

        Returns:
            Optional[Dict[str, Any]]: Zhipu-formatted image_url block or None if invalid
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

        # Return inline_data format to keep consistency throughout the pipeline
        # The format will be converted to image_url at API call time if needed
        return {
            "type": "image",
            "inline_data": {
                "mime_type": mime_type,
                "data": data
            }
        }

    @staticmethod
    def _format_tool_result(content: Any) -> Union[str, List[Dict[str, Any]]]:
        """
        Format tool result content for Zhipu API.

        Transforms tool execution results into Zhipu API compatible format.
        Extracts llm_content from standardized ToolResult objects and formats
        according to Zhipu API requirements.

        For multimodal content (images), returns a list format that will be
        converted to image_url format by _convert_inline_data_to_image_url.

        Args:
            content: Tool execution result with standardized parts format:
                - llm_content.parts: List of content parts (text and/or inline_data)
                - status: Operation outcome ("success" | "error")
                - message: User-facing summary

        Returns:
            Union[str, List[Dict[str, Any]]]:
                - str: Formatted text content for text-only results
                - List: Multimodal content parts with text and inline_data

        Example:
            # ToolResult with text content
            result = {"status": "success", "llm_content": {"parts": [{"type": "text", "text": "result"}]}}
            # Returns: 'result'

            # Result with image content (multimodal)
            result = {"llm_content": {"parts": [{"type": "inline_data", "mime_type": "image/png", "data": "..."}]}}
            # Returns: [{"type": "text", "text": "Image content:"}, {"type": "image", "inline_data": {...}}]
        """
        # All tools use standardized parts format
        llm_content = content["llm_content"]
        content_parts = llm_content["parts"]
        text_parts = []
        image_parts = []

        for part in content_parts:
            part_type = part["type"]

            if part_type == "text":
                # Collect text content (including empty strings for empty files)
                text_content = part.get("text", "")
                # Always include text content, even if empty
                # Empty files are valid and LLM should see them as empty
                text_parts.append(text_content)
            elif part_type == "inline_data":
                # Collect inline_data for multimodal content
                # Format for _convert_inline_data_to_image_url processing
                image_parts.append({
                    "type": "image",
                    "inline_data": {
                        "mime_type": part.get("mime_type", "image/png"),
                        "data": part.get("data", "")
                    }
                })

        # If we have image content, return multimodal format
        if image_parts:
            result_parts: List[Dict[str, Any]] = []

            # Add text description if available
            if text_parts:
                combined_text = "\n".join(text_parts)
                result_parts.append({"type": "text", "text": combined_text})
            else:
                # Add minimal text for context when no text provided
                result_parts.append({"type": "text", "text": "Image content from tool result:"})

            # Add all image parts
            result_parts.extend(image_parts)

            return result_parts

        # Return combined text for text-only results
        if text_parts:
            return "\n".join(text_parts)

        return '{"status": "content processed"}'


__all__ = ['ZhipuMessageFormatter']
