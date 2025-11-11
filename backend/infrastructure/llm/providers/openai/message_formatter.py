"""
OpenAI Responses API Message Formatter

Handles conversion of internal message formats to OpenAI Responses API format.
This formatter extends ChatCompletionsMessageFormatter with Responses API-specific methods.

The OpenAI provider uses the Responses API which has a different format from Chat Completions:
- Chat Completions API: Standard role/content/tool_calls format
- Responses API: Uses types like "message", "reasoning", "function_call", "function_call_output"

This formatter:
1. Inherits Chat Completions formatting from ChatCompletionsMessageFormatter
2. Adds Responses API-specific conversion methods (to_response_input, etc.)

Workflow:
- Internal messages → Chat Completions format (inherited methods)
- Chat Completions format → Responses API format (methods below)
"""

import json
from typing import List, Dict, Any, Optional
from backend.infrastructure.llm.shared.chat_completions_formatter import ChatCompletionsMessageFormatter


class OpenAIMessageFormatter(ChatCompletionsMessageFormatter):
    """
    Format messages for OpenAI Responses API consumption

    Extends ChatCompletionsMessageFormatter with Responses API-specific conversion methods.
    The OpenAI provider workflow:
    1. Convert internal messages to Chat Completions format (inherited)
    2. Convert Chat Completions format to Responses API input format (methods below)
    """

    # ------------------------------------------------------------------
    # Responses API helpers
    # ------------------------------------------------------------------

    @staticmethod
    def to_response_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert formatted OpenAI chat messages to Responses API input items.

        Args:
            messages: Mixed format - either:
                1. response.output items (already in Responses API format)
                2. Chat Completions format messages (role/content/tool_calls)

        Returns:
            List of ResponseInputItem dictionaries compatible with Responses API.
        """
        response_items: List[Dict[str, Any]] = []

        for message in messages:
            if not isinstance(message, dict):
                continue

            # Check if this is a response.output item that needs conversion
            msg_type = message.get("type")

            # Handle response.output items
            if msg_type == "message":
                # Convert response.output message to input format
                converted = OpenAIMessageFormatter._convert_output_message_to_input(message)
                if converted:
                    response_items.append(converted)
                continue
            elif msg_type == "reasoning":
                # Convert reasoning to input message format
                converted = OpenAIMessageFormatter._convert_reasoning_to_input(message)
                if converted:
                    response_items.append(converted)
                continue
            elif msg_type == "function_call":
                # Clean response.output function_call for input
                cleaned = OpenAIMessageFormatter._clean_function_call_for_input(message)
                response_items.append(cleaned)
                continue
            elif msg_type == "function_call_output":
                # Function call outputs can be used as-is
                response_items.append(message)
                continue

            # Convert Chat Completions format to Responses API format
            role = message.get("role")

            if role == "tool":
                tool_output = OpenAIMessageFormatter._convert_tool_result_to_input_item(message)
                if tool_output:
                    response_items.append(tool_output)
                continue

            if role not in {"user", "assistant", "system", "developer"}:
                role = "user"

            content_parts = OpenAIMessageFormatter._convert_content_to_input_parts(message.get("content"))
            if not content_parts:
                content_parts = [{"type": "input_text", "text": ""}]

            # Responses API format: regular messages don't have "type" field
            # Only function_call_output has "type"
            # Content should be string for text-only, array for multimodal
            if len(content_parts) == 1 and content_parts[0].get("type") == "input_text":
                # Text-only: use string format
                content_value = content_parts[0].get("text", "")
            else:
                # Multimodal: use array format
                content_value = content_parts

            response_items.append({
                "role": role,
                "content": content_value
            })

            # Append tool call metadata after assistant messages
            if role == "assistant" and message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    tool_call_item = OpenAIMessageFormatter._convert_tool_call_to_input_item(tool_call)
                    if tool_call_item:
                        response_items.append(tool_call_item)

        return response_items

    @staticmethod
    def _convert_content_to_input_parts(content: Any) -> List[Dict[str, Any]]:
        """Convert chat message content into Responses API content parts."""
        if content is None:
            return []

        if isinstance(content, str):
            return [{"type": "input_text", "text": content}]

        parts: List[Dict[str, Any]] = []

        if isinstance(content, list):
            for block in content:
                part = OpenAIMessageFormatter._convert_block_to_input_part(block)
                if part:
                    parts.append(part)
        else:
            parts.append({"type": "input_text", "text": str(content)})

        return parts

    @staticmethod
    def _convert_block_to_input_part(block: Any) -> Optional[Dict[str, Any]]:
        """Convert a single content block into Responses API input format."""
        if isinstance(block, str):
            return {"type": "input_text", "text": block}

        if not isinstance(block, dict):
            return {"type": "input_text", "text": str(block)}

        block_type = block.get("type")

        if block_type == "text":
            return {"type": "input_text", "text": block.get("text", "")}

        if block_type == "thinking":
            thinking_text = block.get("thinking", "")
            if thinking_text:
                return {"type": "input_text", "text": f"<thinking>{thinking_text}</thinking>"}
            return {"type": "input_text", "text": ""}

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

        if block_type == "image":
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

        # Fallback for blocks with 'text' field but no explicit type
        if "text" in block:
            return {"type": "input_text", "text": str(block.get("text", ""))}

        return None

    @staticmethod
    def _convert_tool_call_to_input_item(tool_call: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert assistant tool call metadata into Responses API function_call item."""
        if not isinstance(tool_call, dict):
            return None

        function_data = tool_call.get("function", {})
        tool_name = function_data.get("name")
        if not tool_name:
            return None

        call_id = tool_call.get("id") or tool_name
        arguments = function_data.get("arguments", {})

        if isinstance(arguments, str):
            arguments_str = arguments
        else:
            try:
                arguments_str = json.dumps(arguments)
            except (TypeError, ValueError):
                arguments_str = str(arguments)

        return {
            "type": "function_call",
            "id": call_id,
            "call_id": call_id,
            "name": tool_name,
            "arguments": arguments_str
        }

    @staticmethod
    def _convert_tool_result_to_input_item(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert tool result messages into Responses API function_call_output item."""
        tool_call_id = message.get("tool_call_id")
        if not tool_call_id:
            return None

        content = message.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    text_parts.append(str(block.get("text", "")))
                else:
                    text_parts.append(str(block))
            output_text = "\n".join(filter(None, text_parts))
        else:
            output_text = str(content) if content is not None else ""

        return {
            "type": "function_call_output",
            "call_id": tool_call_id,
            "output": output_text
        }

    @staticmethod
    def _convert_output_message_to_input(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert response.output message item to input format.

        response.output format:
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "..."}],
            "status": "completed",
            "id": "msg_xxx"
        }

        input format:
        {
            "role": "assistant",
            "content": "..." or [{"type": "input_text", "text": "..."}]
        }
        """
        role = message.get("role")
        if not role:
            return None

        content = message.get("content", [])

        # Convert output_text to input_text
        if isinstance(content, list):
            # Handle empty content array
            if not content:
                content_value = ""
            else:
                converted_content = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")
                        if block_type == "output_text":
                            text_value = block.get("text", "")
                            converted_content.append({"type": "input_text", "text": text_value})
                        elif block_type == "input_text":
                            # Already input format
                            converted_content.append(block)
                        else:
                            # Unknown type, keep as-is
                            converted_content.append(block)
                    elif isinstance(block, str):
                        converted_content.append({"type": "input_text", "text": block})

                # Simplify if only one text block
                if len(converted_content) == 1 and converted_content[0].get("type") == "input_text":
                    content_value = converted_content[0].get("text", "")
                elif converted_content:
                    content_value = converted_content
                else:
                    content_value = ""
        elif isinstance(content, str):
            content_value = content
        else:
            content_value = str(content) if content else ""

        return {
            "role": role,
            "content": content_value
        }

    @staticmethod
    def _clean_function_call_for_input(message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean response.output function_call for use in input.

        Removes fields that are only valid in response.output:
        - id (only call_id is needed in input)
        - status (not needed in input)

        Ensures required fields are present with defaults:
        - arguments: Required by API, defaults to empty string
        """
        import json

        # Get arguments with fallback to empty dict
        arguments = message.get("arguments")

        # Convert arguments to string format if it's a dict
        if isinstance(arguments, dict):
            try:
                arguments = json.dumps(arguments)
            except (TypeError, ValueError):
                arguments = "{}"
        elif arguments is None:
            arguments = "{}"
        else:
            arguments = str(arguments)

        return {
            "type": "function_call",
            "call_id": message.get("call_id"),
            "name": message.get("name"),
            "arguments": arguments
        }

    @staticmethod
    def _convert_reasoning_to_input(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert response.output reasoning item to input format.

        response.output format:
        {
            "type": "reasoning",
            "id": "reasoning_xxx",
            "summary": [{"type": "summary_text", "text": "..."}],
            "status": "completed",
            "encrypted_content": null
        }

        Input format:
        {
            "type": "reasoning",
            "id": "reasoning_xxx",
            "summary": [{"type": "summary_text", "text": "..."}]
        }

        Note: 'id' field IS required in input (contrary to initial documentation).
        Only remove output-only fields: status, encrypted_content.
        """
        summary = message.get("summary", [])
        reasoning_id = message.get("id")

        if not summary or not reasoning_id:
            return None

        # Keep type, id, and summary - only remove status and encrypted_content
        return {
            "type": "reasoning",
            "id": reasoning_id,
            "summary": summary
        }
