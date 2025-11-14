"""
OpenAI Response Processor

Handles processing of OpenAI API responses including text extraction,
tool call detection, and response formatting for storage.
"""

import json
from typing import List, Dict, Any, Optional
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseReasoningItem,
)
from openai.types.responses.response_output_text import ResponseOutputText
from backend.domain.models.messages import AssistantMessage
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor


class OpenAIResponseProcessor(BaseResponseProcessor):
    """
    Process OpenAI API responses and extract relevant information.
    """

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from OpenAI Responses API result.

        Args:
            response: OpenAI Responses API response object

        Returns:
            Extracted text content as a single string.
        """
        if not isinstance(response, Response) or not response.output:
            return ""

        text_segments: List[str] = []

        for item in response.output:
            if isinstance(item, ResponseOutputMessage):
                for part in item.content:
                    if isinstance(part, ResponseOutputText):
                        text_segments.append(part.text)

        return "".join(text_segments)

    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls.
        """
        if not isinstance(response, Response) or not response.output:
            return False

        return any(isinstance(item, ResponseFunctionToolCall) for item in response.output)

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from OpenAI Responses API result.
        """
        if not isinstance(response, Response) or not response.output:
            return []

        tool_calls: List[Dict[str, Any]] = []

        for item in response.output:
            if not isinstance(item, ResponseFunctionToolCall):
                continue

            try:
                arguments = item.arguments
                if isinstance(arguments, str):
                    try:
                        parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        parsed_args = arguments
                else:
                    parsed_args = arguments

                import uuid

                tool_call_id = item.call_id or item.id or str(uuid.uuid4())
                tool_calls.append({
                    "name": item.name,
                    "arguments": parsed_args,
                    "id": tool_call_id
                })
            except Exception as exc:
                print(f"[WARNING] Failed to parse tool call: {exc}")
                continue

        return tool_calls

    @staticmethod
    def format_response_for_storage(
        response,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AssistantMessage:
        """
        Format OpenAI Responses API output for storage in message history.
        """
        if not isinstance(response, Response):
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        content_blocks: List[Dict[str, Any]] = []

        # Extract reasoning and text content in a single pass (optimization)
        # This avoids redundant iteration over response.output
        if response.output:
            text_segments: List[str] = []

            for item in response.output:
                # Extract reasoning content
                if isinstance(item, ResponseReasoningItem):
                    # Extract all summary text parts
                    reasoning_texts = []
                    for summary in item.summary:
                        summary_text = getattr(summary, "text", "")
                        if summary_text:
                            reasoning_texts.append(summary_text)

                    # Combine all reasoning text into single thinking block
                    if reasoning_texts:
                        content_blocks.append({
                            "type": "thinking",
                            "thinking": "\n".join(reasoning_texts)
                        })

                # Extract text content
                elif isinstance(item, ResponseOutputMessage):
                    for part in item.content:
                        if isinstance(part, ResponseOutputText):
                            text_segments.append(part.text)

            # Add combined text content if any
            if text_segments:
                combined_text = "".join(text_segments)
                if combined_text:
                    content_blocks.append({"type": "text", "text": combined_text})

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = OpenAIResponseProcessor.extract_tool_calls(response)

        # Add tool_use blocks to content array (following Gemini/Anthropic/Kimi pattern)
        # This ensures frontend can render tool calls correctly
        if tool_calls:
            for tool_call in tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tool_call['id'],
                    "name": tool_call['name'],
                    "input": tool_call['arguments']
                })

        message = AssistantMessage(
            role="assistant",
            content=content_blocks if content_blocks else [{"type": "text", "text": ""}]
        )

        # Note: tool_calls are already represented as tool_use blocks in content array
        # No need to set message.tool_calls attribute (which doesn't exist in the model)

        return message

    @staticmethod
    def format_response_for_context(response) -> List[Dict[str, Any]]:
        """
        Format OpenAI Responses API output for working context.

        Processes response.output items and converts them to Responses API input format
        for use in subsequent API calls.

        This method centralizes the formatting logic previously in
        context_manager.add_response() for better separation of concerns.

        Args:
            response: OpenAI API Response object

        Returns:
            List of context items ready to append to working_contents.
            Returns empty list if response is invalid.

            Note: Unlike other providers, OpenAI returns a LIST because one response
            can produce multiple context items (message, reasoning, function_call).
        """
        if not isinstance(response, Response):
            return []

        if not response.output:
            return []

        context_items: List[Dict[str, Any]] = []

        # Process each output item and convert to input format
        for item in response.output:
            # Convert Pydantic model to dict
            item_dict = item.model_dump(mode='json', exclude_none=False)
            item_type = item_dict.get("type")

            # Handle message items (assistant responses)
            if item_type == "message":
                role = item_dict.get("role")
                if not role:
                    continue

                content = item_dict.get("content", [])

                # Extract text content from response.output format
                if isinstance(content, list):
                    if not content:
                        content_value = ""
                    else:
                        # Extract only text content (skip reasoning)
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "output_text":
                                text_parts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                text_parts.append(block)
                        content_value = "".join(text_parts)
                elif isinstance(content, str):
                    content_value = content
                else:
                    content_value = str(content) if content else ""

                context_items.append({
                    "role": role,
                    "content": content_value
                })

            # Handle reasoning items
            # Note: Current request's reasoning MUST be kept for pairing with function_call
            # Historical reasoning (from DB) is NOT loaded (format_single_message skips thinking)
            # This dual approach works because API only requires pairing in current request
            elif item_type == "reasoning":
                summary = item_dict.get("summary", [])
                reasoning_id = item_dict.get("id")

                # Keep reasoning item if it has an ID (required for pairing with function_call)
                # Note: Empty summary ([]) should still be kept to maintain pairing
                if reasoning_id:
                    # Keep type, id, and summary for input
                    context_items.append({
                        "type": "reasoning",
                        "id": reasoning_id,
                        "summary": summary if summary else []
                    })

            # Handle function_call items
            elif item_type == "function_call":
                # Ensure arguments field exists
                if 'arguments' not in item_dict or item_dict['arguments'] is None:
                    item_dict['arguments'] = "{}"

                # Convert arguments to string if needed
                arguments = item_dict.get("arguments")
                if isinstance(arguments, dict):
                    try:
                        arguments = json.dumps(arguments)
                    except (TypeError, ValueError):
                        arguments = "{}"
                elif arguments is None:
                    arguments = "{}"
                else:
                    arguments = str(arguments)

                # Use correct IDs for input format:
                # - id: fc_xxx (required for input[].id field)
                # - call_id: call_xxx (used to match with function_call_output)
                context_items.append({
                    "type": "function_call",
                    "id": item_dict.get("id"),           # fc_xxx - required by API
                    "call_id": item_dict.get("call_id"), # call_xxx - for matching results
                    "name": item_dict.get("name"),
                    "arguments": arguments
                })

            # Note: function_call_output branch intentionally removed
            # - OpenAI API does not return function_call_output in response.output
            # - Tool results are added via add_tool_result() → format_tool_result_for_context()
            # - This prevents duplication and aligns with other providers' architecture

        return context_items

    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from OpenAI response.

        Note: OpenAI doesn't have built-in web search like Gemini. Placeholder for MCP-based sources.
        """
        return []
