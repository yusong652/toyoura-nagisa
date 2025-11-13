"""
Chat Completions Message Formatter

Handles conversion of internal message formats to standard OpenAI Chat Completions API format.
This formatter is used by providers that implement the standard Chat Completions API,
including OpenAI and OpenRouter.

The Chat Completions API format differs from OpenAI's Responses API:
- Chat Completions: Standard role/content/tool_calls format
- Responses API: Uses types like "message", "reasoning", "function_call", etc.

Supports multimodal content, tool calls, and message history processing.

Note: Kimi uses a separate formatter (kimi/message_formatter.py) that supports reasoning_content.
"""

import json
from typing import List, Dict, Any, Union, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class ChatCompletionsMessageFormatter(BaseMessageFormatter):
    """
    Format messages for standard Chat Completions API consumption

    Converts internal message objects to Chat Completions API format while preserving
    all content types including text, images, tool calls, and tool results.

    This formatter is suitable for:
    - OpenAI Chat Completions API
    - OpenRouter API
    - Other standard OpenAI-compatible APIs

    Note: This formatter does NOT support reasoning_content field.
    Kimi uses KimiMessageFormatter which supports reasoning_content for k2-thinking models.
    """

    @staticmethod
    def format_messages(
        messages: List[BaseMessage],
        preserve_thinking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Convert internal messages to Chat Completions API format

        Args:
            messages: List of internal message objects
            preserve_thinking: Whether to preserve thinking content in context

        Returns:
            List of Chat Completions-formatted message dictionaries
        """
        formatted_messages = []

        for msg in messages:
            # Handle regular messages with multimodal content
            if isinstance(msg.content, list):
                chat_content = ChatCompletionsMessageFormatter._format_multimodal_content(
                    msg.content, preserve_thinking
                )
                formatted_messages.append({
                    "role": msg.role, # type: ignore
                    "content": chat_content
                })
            else:
                # Simple text content
                text_content = str(msg.content) if msg.content else ""
                formatted_messages.append({
                    "role": msg.role, # type: ignore
                    "content": text_content
                })

        return formatted_messages

    @staticmethod
    def format_single_message(
        message: BaseMessage,
        preserve_thinking: bool = True
    ) -> Dict[str, Any]:
        """
        Format a single BaseMessage to Chat Completions API format

        Args:
            message: Single internal message object
            preserve_thinking: Whether to preserve thinking content

        Returns:
            Dict[str, Any]: Chat Completions-formatted message dictionary
        """
        if message is None:
            return {}

        # Handle regular messages with multimodal content
        if isinstance(message.content, list):
            chat_content = ChatCompletionsMessageFormatter._format_multimodal_content(
                message.content, preserve_thinking
            )
            return {
                "role": message.role, # type: ignore
                "content": chat_content
            }
        else:
            # Simple text content
            text_content = str(message.content) if message.content else ""
            return {
                "role": message.role, # type: ignore
                "content": text_content
            }

    @staticmethod
    def _format_multimodal_content(
        content: List[Dict[str, Any]],
        preserve_thinking: bool = True
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        Format multimodal content for Chat Completions API

        Args:
            content: List of content blocks
            preserve_thinking: Whether to preserve thinking content

        Returns:
            Chat Completions-formatted content - either string for text-only or array for multimodal
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
                image_block = ChatCompletionsMessageFormatter._format_image_block(inline_data)
                if image_block:
                    formatted_content.append(image_block)
                    has_non_text_content = True

            # Handle pre-formatted image_url content
            elif block.get("type") == "image_url":
                formatted_content.append(block)
                has_non_text_content = True

            # Handle thinking content
            # Include thinking content directly without tags to prevent few-shot contamination
            elif block.get("type") == "thinking" and preserve_thinking:
                thinking_text = block.get("thinking", "")
                # Always include thinking content, even if it's just "\n"
                formatted_content.append({
                    "type": "text",
                    "text": thinking_text
                })
                # Mark that we have thinking content to prevent merging
                has_non_text_content = True

            # Skip tool_use and tool_result blocks (cross-provider compatibility)
            # These blocks are from Anthropic/Gemini format and should be ignored
            # when loading history with Chat Completions API providers
            elif block.get("type") in ["tool_use", "tool_result"]:
                continue

        # Return optimization for text-only content
        # IMPORTANT: Don't merge if we have thinking content, to keep thinking and text separate
        if not has_non_text_content:
            text_parts = [block.get("text", "") for block in formatted_content if block.get("type") == "text"]
            combined_text = "".join(text_parts)
            # If content only had tool_use/tool_result blocks (cross-provider format mismatch),
            # return placeholder text to avoid empty assistant messages
            if not combined_text:
                return "[Tool execution completed]"
            return combined_text

        return formatted_content

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
