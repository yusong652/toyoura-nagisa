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

        # Include reasoning summary as thinking content if available
        if response.output:
            for item in response.output:
                if isinstance(item, ResponseReasoningItem):
                    for summary in item.summary:
                        summary_text = getattr(summary, "text", "")
                        if summary_text:
                            content_blocks.append({
                                "type": "thinking",
                                "thinking": summary_text
                            })

        text_content = OpenAIResponseProcessor.extract_text_content(response)
        if text_content:
            content_blocks.append({"type": "text", "text": text_content})

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
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from OpenAI response.

        Note: OpenAI doesn't have built-in web search like Gemini. Placeholder for MCP-based sources.
        """
        if debug:
            print("[DEBUG] OpenAI doesn't support built-in web search - using MCP tools instead")

        return []
