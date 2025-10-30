"""
OpenAI Message Formatter

Handles conversion of internal message formats to OpenAI API format.
Supports multimodal content, tool calls, and message history processing.
"""

import json
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
                    "role": msg.role, # type: ignore
                    "content": openai_content
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
                "role": message.role, # type: ignore
                "content": openai_content
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
        Format tool result content for OpenAI API.

        Transforms tool execution results into OpenAI API compatible format.
        Extracts llm_content from standardized ToolResult objects and formats
        according to OpenAI's content requirements.

        Args:
            content: Tool execution result with standardized parts format:
                - llm_content.parts: List of content parts (text and/or inline_data)
                - status: Operation outcome ("success" | "error")
                - message: User-facing summary

        Returns:
            str: Formatted text content for OpenAI API
                Note: OpenAI tool messages only support text, inline_data is omitted

        Example:
            # ToolResult with text content
            result = {"status": "success", "llm_content": {"parts": [{"type": "text", "text": "result"}]}}
            # Returns: 'result'

            # Result with image content (OpenAI limitation)
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
                # Collect text content
                text_content = part.get("text", "")
                if text_content:
                    text_parts.append(text_content)
            elif part_type == "inline_data":
                # OpenAI tool messages only support text, skip inline_data
                # Note: This is an API limitation, not a choice
                pass

        # Return combined text or indicate content was processed
        if text_parts:
            return "\n".join(text_parts)

        return '{"status": "content processed"}'

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
        """
        return {
            "type": "function_call",
            "call_id": message.get("call_id"),
            "name": message.get("name"),
            "arguments": message.get("arguments")
        }

    @staticmethod
    def _convert_reasoning_to_input(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert response.output reasoning item to input format.

        response.output format:
        {
            "type": "reasoning",
            "summary": [{"type": "summary_text", "text": "..."}],
            "status": "completed",
            "id": "reasoning_xxx"
        }

        We include reasoning as assistant messages with <thinking> tags.
        """
        summary = message.get("summary", [])

        if not summary:
            return None

        # Extract reasoning text from summary
        reasoning_parts = []
        for part in summary:
            if isinstance(part, dict):
                if part.get("type") == "summary_text":
                    text = part.get("text", "")
                    if text:
                        reasoning_parts.append(text)

        if not reasoning_parts:
            return None

        # Combine reasoning text
        reasoning_text = "\n".join(reasoning_parts)

        return {
            "role": "assistant",
            "content": f"<thinking>{reasoning_text}</thinking>"
        }
