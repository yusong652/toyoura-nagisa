"""
Kimi (Moonshot) Message Formatter

Handles conversion of internal message formats to Kimi API format.
Kimi uses OpenAI Chat Completions API format with additional reasoning_content support
for k2-thinking models.

Supports multimodal content, tool calls, reasoning content, and message history processing.
"""

import json
from typing import List, Dict, Any, Union, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class KimiMessageFormatter(BaseMessageFormatter):
    """
    Format messages for Kimi (Moonshot) API consumption

    Converts internal message objects to Kimi API format while preserving
    all content types including text, images, tool calls, reasoning content, and tool results.

    This formatter is specifically designed for Kimi API which supports:
    - Standard Chat Completions format
    - reasoning_content field for k2-thinking models
    - Tool calling and multimodal content
    """

    @staticmethod
    def format_messages(
        messages: List[BaseMessage],
    ) -> List[Dict[str, Any]]:
        """
        Convert internal messages to Chat Completions API format.

        Always preserves thinking content for cross-turn reasoning continuity.

        Args:
            messages: List of internal message objects

        Returns:
            List of Chat Completions-formatted message dictionaries
        """
        formatted_messages = []

        for msg in messages:
            # format_single_message may return a dict or a list (for tool_result blocks)
            formatted = KimiMessageFormatter.format_single_message(msg)

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
        Format a single BaseMessage to Chat Completions API format.

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
        thinking_blocks = []
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
                    thinking_blocks.append(thinking_content)

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
                image_block = KimiMessageFormatter._format_image_block(inline_data)
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
                    formatted_content = KimiMessageFormatter._format_tool_result({
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

        # Add reasoning_content if present (separate field for thinking models like Kimi k2-thinking)
        # thinking_blocks now contains strings instead of dicts
        if thinking_blocks:
            # Combine all thinking blocks into single reasoning_content
            result["reasoning_content"] = "".join(thinking_blocks)

        # Build content field
        content_value: Union[str, List[Dict[str, Any]]]

        has_images = len(image_blocks) > 0
        has_tool_calls = len(tool_use_blocks) > 0
        has_text = len(text_blocks) > 0

        if has_images:
            # Multimodal content: return array
            content_value = text_blocks + image_blocks
        elif has_text:
            # Text only: return as string
            text_parts = [block.get("text", "") for block in text_blocks]
            content_value = "".join(text_parts)
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
        Format inline_data into Chat Completions image_url block.

        Args:
            inline_data: Dictionary containing image data and mime_type

        Returns:
            Optional[Dict[str, Any]]: Chat Completions-formatted image_url block or None if invalid
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
        Format tool result content for Chat Completions API.

        Transforms tool execution results into Chat Completions API compatible format.
        Extracts llm_content from standardized ToolResult objects and formats
        according to Chat Completions API requirements.

        Args:
            content: Tool execution result with standardized parts format:
                - llm_content.parts: List of content parts (text and/or inline_data)
                - status: Operation outcome ("success" | "error")
                - message: User-facing summary

        Returns:
            str: Formatted text content for Chat Completions API
                Note: Chat Completions tool messages only support text, inline_data is omitted

        Example:
            # ToolResult with text content
            result = {"status": "success", "llm_content": {"parts": [{"type": "text", "text": "result"}]}}
            # Returns: 'result'

            # Result with image content (Chat Completions API limitation)
            result = {"llm_content": {"parts": [{"type": "text", "text": "image"}, {"type": "inline_data", ...}]}}
            # Returns: 'image' (inline_data omitted due to API constraints)
        """
        # All tools use standardized parts format
        llm_content = content["llm_content"]
        content_parts = llm_content["parts"]
        text_parts = []

        for part in content_parts:
            part_type = part["type"]

            if part_type == "text":
                # Collect text content (including empty strings for empty files)
                text_content = part.get("text", "")
                # Always include text content, even if empty
                # Empty files are valid and LLM should see them as empty
                text_parts.append(text_content)
            elif part_type == "inline_data":
                # Chat Completions tool messages only support text, skip inline_data
                # Note: This is an API limitation, not a choice
                pass

        # Return combined text or indicate content was processed
        if text_parts:
            return "\n".join(text_parts)

        return '{"status": "content processed"}'
