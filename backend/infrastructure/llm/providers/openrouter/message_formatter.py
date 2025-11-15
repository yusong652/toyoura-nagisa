"""
OpenRouter Message Formatter

Handles conversion of internal message formats to OpenRouter Chat Completions API format.
OpenRouter uses standard Chat Completions API with additional support for reasoning tokens.

Key differences from standard Chat Completions:
- Extracts thinking blocks and adds them as 'reasoning' field for thinking models
- Preserves thinking content in context for proper reasoning model behavior
"""

from typing import List, Dict, Any, Union, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class OpenRouterMessageFormatter(BaseMessageFormatter):
    """
    Format messages for OpenRouter Chat Completions API with reasoning support.

    Converts internal message objects to OpenRouter API format while:
    - Preserving all content types (text, images, tool calls, tool results)
    - Extracting thinking blocks and adding them as 'reasoning' field
    - Supporting reasoning tokens for thinking models
    """

    @staticmethod
    def format_messages(
        messages: List[BaseMessage],
        preserve_thinking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Convert internal messages to OpenRouter Chat Completions API format.

        Args:
            messages: List of internal message objects
            preserve_thinking: Whether to preserve thinking content in context

        Returns:
            List of OpenRouter-formatted message dictionaries with reasoning fields
        """
        formatted_messages = []

        for msg in messages:
            formatted_msg = OpenRouterMessageFormatter.format_single_message(
                msg, preserve_thinking
            )
            if formatted_msg:
                formatted_messages.append(formatted_msg)

        return formatted_messages

    @staticmethod
    def format_single_message(
        message: BaseMessage,
        preserve_thinking: bool = True
    ) -> Dict[str, Any]:
        """
        Format a single BaseMessage to OpenRouter Chat Completions API format.

        Args:
            message: Single internal message object
            preserve_thinking: Whether to preserve thinking content

        Returns:
            Dict[str, Any]: OpenRouter-formatted message dictionary with reasoning field
        """
        if message is None:
            return {}

        # Handle regular messages with multimodal content
        if isinstance(message.content, list):
            chat_content, reasoning_content = OpenRouterMessageFormatter._format_multimodal_content(
                message.content, preserve_thinking
            )

            result = {
                "role": message.role,  # type: ignore
                "content": chat_content
            }

            # Add reasoning field if thinking content was extracted
            if reasoning_content and preserve_thinking:
                result["reasoning"] = reasoning_content

            return result
        else:
            # Simple text content
            text_content = str(message.content) if message.content else ""
            return {
                "role": message.role,  # type: ignore
                "content": text_content
            }

    @staticmethod
    def _format_multimodal_content(
        content: List[Dict[str, Any]],
        preserve_thinking: bool = True
    ) -> tuple[Union[str, List[Dict[str, Any]]], Optional[str]]:
        """
        Format multimodal content for OpenRouter Chat Completions API.

        Args:
            content: List of content blocks
            preserve_thinking: Whether to preserve thinking content

        Returns:
            Tuple of (formatted_content, reasoning_content):
            - formatted_content: Chat Completions-formatted content (string or list)
            - reasoning_content: Extracted thinking content for reasoning field (or None)
        """
        formatted_content = []
        thinking_parts = []  # Collect thinking content for reasoning field
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
                image_block = OpenRouterMessageFormatter._format_image_block(inline_data)
                if image_block:
                    formatted_content.append(image_block)
                    has_non_text_content = True

            # Handle pre-formatted image_url content
            elif block.get("type") == "image_url":
                formatted_content.append(block)
                has_non_text_content = True

            # Handle thinking content
            # Extract for reasoning field ONLY (not in content to avoid duplication)
            elif block.get("type") == "thinking" and preserve_thinking:
                thinking_text = block.get("thinking", "")

                # Collect for reasoning field
                if thinking_text:
                    thinking_parts.append(thinking_text)

            # Skip tool_use and tool_result blocks (cross-provider compatibility)
            # These blocks are from Anthropic/Gemini format and should be ignored
            # when loading history with Chat Completions API providers
            elif block.get("type") in ["tool_use", "tool_result"]:
                continue

        # Combine thinking parts into reasoning field
        reasoning_content = "\n".join(thinking_parts) if thinking_parts else None

        # Return optimization for text-only content
        # IMPORTANT: Don't merge if we have thinking content, to keep thinking and text separate
        if not has_non_text_content:
            text_parts = [block.get("text", "") for block in formatted_content if block.get("type") == "text"]
            combined_text = "".join(text_parts)
            # If content only had tool_use/tool_result blocks (cross-provider format mismatch),
            # return placeholder text to avoid empty assistant messages
            if not combined_text:
                return ("[Tool execution completed]", reasoning_content)
            return (combined_text, reasoning_content)

        return (formatted_content, reasoning_content)

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


__all__ = ['OpenRouterMessageFormatter']
