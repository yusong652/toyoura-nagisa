"""
OpenAI Responses API Message Formatter

Handles conversion of internal message formats to OpenAI Responses API format.
This formatter directly converts BaseMessage objects to Responses API input format.

The OpenAI Responses API uses specialized item types:
- Messages: role + content (text or multimodal)
- Reasoning: type="reasoning" with summary field
- Function calls: type="function_call" with call_id, name, arguments
- Function outputs: type="function_call_output" with call_id, output

This formatter provides:
1. Direct BaseMessage → Responses API input format conversion
2. Response output → input format conversion for context management
3. Tool result formatting for working context

Architecture:
- format_messages: Converts BaseMessage list to API input items
- format_single_message: Converts single BaseMessage to API input item(s)
- format_tool_result_for_context: Formats tool results for context
- Internal helpers for response.output conversion
"""

import json
from typing import List, Dict, Any, Optional, Union
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class OpenAIMessageFormatter(BaseMessageFormatter):
    """
    Format messages for OpenAI Responses API consumption

    Directly converts internal message format to Responses API format.
    Does NOT use Chat Completions format as intermediate step.

    Key differences from Chat Completions API:
    - Uses string content only (no array format with types)
    - Thinking/reasoning handled separately by API
    - Tool calls use function_call/function_call_output types
    """

    @staticmethod
    def format_messages(
        messages: List[BaseMessage],
        preserve_thinking: bool = False  # Ignored - OpenAI handles reasoning separately
    ) -> List[Dict[str, Any]]:
        """
        Convert internal messages to Responses API input format.

        This method directly formats BaseMessage objects into OpenAI Responses API
        input format, eliminating the need for intermediate conversion steps.

        Args:
            messages: List of internal message objects
            preserve_thinking: Ignored - OpenAI has separate reasoning mechanism

        Returns:
            List of input items for OpenAI Responses API
        """
        response_items = []

        for msg in messages:
            formatted = OpenAIMessageFormatter.format_single_message(msg)
            # format_single_message may return a list (for messages with tool calls)
            if isinstance(formatted, list):
                response_items.extend(formatted)
            elif formatted:
                response_items.append(formatted)

        return response_items

    @staticmethod
    def format_single_message(
        message: BaseMessage,
        preserve_thinking: bool = False  # Ignored
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Format a single BaseMessage to Responses API input format.

        Directly converts BaseMessage to OpenAI Responses API input items.
        Handles text content, tool calls, tool results, and multimodal content.

        Args:
            message: Single internal message object
            preserve_thinking: Ignored - OpenAI handles reasoning separately

        Returns:
            - Single Dict for regular messages
            - List[Dict] for messages with tool calls/results
        """
        if message is None:
            return {}

        role = message.role  # type: ignore

        # Handle different content formats
        if not isinstance(message.content, list):
            # Simple text content
            content = str(message.content) if message.content else ""
            return {
                "role": role,
                "content": content
            }

        # Extract different block types
        text_parts = []
        tool_use_blocks = []
        tool_result_blocks = []
        has_images = False

        for block in message.content:
            if isinstance(block, dict):
                block_type = block.get("type")

                # Skip thinking blocks - OpenAI handles reasoning separately
                if block_type == "thinking":
                    continue

                # Collect tool_use blocks (from assistant messages)
                elif block_type == "tool_use":
                    tool_use_blocks.append(block)

                # Collect tool_result blocks (from user messages)
                elif block_type == "tool_result":
                    tool_result_blocks.append(block)

                # Check for image content
                elif block_type in ("image", "image_url", "input_image"):
                    has_images = True
                # Also check for Gemini native format (no type field)
                elif "inline_data" in block:
                    has_images = True

                # Extract text content
                elif block_type == "text" and "text" in block:
                    text_parts.append(str(block.get("text", "")))
                elif "text" in block:
                    text_parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                text_parts.append(block)

        # Build result based on content
        result_items = []

        # Handle multimodal content (with images)
        if has_images:
            # Extract image parts directly
            image_parts = []
            for block in message.content:
                if isinstance(block, dict):
                    image_part = OpenAIMessageFormatter._convert_image_block_to_input(block)
                    if image_part:
                        image_parts.append(image_part)

            # Build multimodal content
            text_content = "".join(text_parts)
            if text_content:
                # For multimodal, prepend text before image parts
                result_items.append({
                    "role": role,
                    "content": [{"type": "input_text", "text": text_content}] + image_parts
                })
            elif image_parts:
                result_items.append({
                    "role": role,
                    "content": image_parts
                })
        else:
            # Text-only content
            text_content = "".join(text_parts)
            if text_content or (not tool_use_blocks and not tool_result_blocks):
                # Always include message if it has text or no tools
                result_items.append({
                    "role": role,
                    "content": text_content
                })

        # Add function_call items for tool_use blocks
        for tool_use in tool_use_blocks:
            # When loading from storage, tool_use.id contains call_xxx (not fc_xxx)
            # We should NOT set the id field with call_xxx as API expects fc_xxx
            # Instead, omit the id field and let API handle it, or use call_id only
            tool_id = tool_use.get("id", "")

            function_call_item = {
                "type": "function_call",
                "call_id": tool_id,  # call_xxx - for matching with function_call_output
                "name": tool_use.get("name", ""),
                "arguments": json.dumps(tool_use.get("input", {}), ensure_ascii=False)
            }
            # Note: We don't set 'id' field here because:
            # 1. Storage format only has call_xxx (from previous API response)
            # 2. API requires id to start with fc_xxx
            # 3. Without id field, API should accept it or generate one

            result_items.append(function_call_item)

        # Add function_call_output items for tool_result blocks
        for tool_result in tool_result_blocks:
            # Extract tool result content
            nested_content = tool_result.get("content", {})
            if isinstance(nested_content, dict) and "parts" in nested_content:
                # Extract text from parts
                text_parts_result = []
                for part in nested_content.get("parts", []):
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts_result.append(part.get("text", ""))
                output_content = "\n".join(text_parts_result)
            else:
                output_content = str(nested_content)

            function_output_item = {
                "type": "function_call_output",
                "call_id": tool_result.get("tool_use_id", ""),
                "output": output_content
            }
            result_items.append(function_output_item)

        # Return single item or list
        if len(result_items) == 1:
            return result_items[0]
        elif result_items:
            return result_items
        else:
            # Empty message
            return {
                "role": role,
                "content": ""
            }

    # ------------------------------------------------------------------
    # Context management helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_tool_result_for_context(
        tool_call_id: str,
        tool_name: str,
        result: Any
    ) -> Dict[str, Any]:
        """
        Format tool result for OpenAI working context.

        Creates function_call_output item for Responses API input.

        Args:
            tool_call_id: Tool call unique identifier
            tool_name: Name of the tool that was executed (unused for OpenAI)
            result: Tool execution result with standardized parts format

        Returns:
            Dict[str, Any]: function_call_output item for Responses API
        """
        # Extract content from standardized ToolResult format
        llm_content = result.get("llm_content", {})
        content_parts = llm_content.get("parts", [])

        # Extract text content from parts
        text_parts = []
        for part in content_parts:
            if isinstance(part, dict) and part.get("type") == "text":
                text_content = part.get("text", "")
                if text_content:
                    text_parts.append(text_content)

        output_text = "\n".join(text_parts) if text_parts else ""

        return {
            "type": "function_call_output",
            "call_id": tool_call_id,
            "output": output_text
        }


    @staticmethod
    def _convert_image_block_to_input(block: Any) -> Optional[Dict[str, Any]]:
        """
        Convert a single image block to Responses API input_image format.

        Handles three image formats:
        1. image_url: External image URL with optional detail level
        2. image: Base64-encoded inline image data (with type field)
        3. inline_data: Gemini native format (without type field)

        Args:
            block: Content block (dict with type and image data)

        Returns:
            input_image block for Responses API, or None if not an image block
        """
        if not isinstance(block, dict):
            # Text content in multimodal should be skipped or handled at higher level
            return None

        block_type = block.get("type")

        # Handle image_url format
        if block_type == "image_url":
            image_url = block.get("image_url", {})
            url = image_url.get("url")
            if not url:
                return None
            image_part: Dict[str, Any] = {"type": "input_image", "image_url": url}
            detail = image_url.get("detail")
            if detail:
                image_part["detail"] = detail
            return image_part

        # Handle image format (with type field) or Gemini native inline_data (without type field)
        if block_type == "image" or "inline_data" in block:
            inline_data = block.get("inline_data", {})
            data = inline_data.get("data")
            if not data:
                return None

            mime_type = inline_data.get("mime_type", "image/png")
            if isinstance(data, bytes):
                import base64
                data = base64.b64encode(data).decode("utf-8")
            if isinstance(data, str):
                data = data.strip().replace("\n", "")

            return {
                "type": "input_image",
                "image_url": f"data:{mime_type};base64,{data}",
                "detail": inline_data.get("detail", "high")
            }

        # Skip text blocks - they should be handled as strings at higher level
        return None
