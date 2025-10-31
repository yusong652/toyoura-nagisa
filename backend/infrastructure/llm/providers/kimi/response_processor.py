"""
Kimi (Moonshot) Response Processor

Handles processing of Kimi API responses using OpenAI Chat Completions API format.

Unlike OpenAI's Responses API, Kimi uses the traditional Chat Completions API
which returns ChatCompletion objects instead of Response objects.
"""

import json
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from backend.domain.models.messages import AssistantMessage
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor
from .debug import KimiDebugger


class KimiResponseProcessor(BaseResponseProcessor):
    """
    Process Kimi API responses using Chat Completions format.

    Kimi uses OpenAI-compatible Chat Completions API (not Responses API),
    so the response structure is ChatCompletion, not Response.
    """

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from Kimi ChatCompletion response.

        Args:
            response: ChatCompletion object from Kimi API

        Returns:
            Extracted text content as a single string.
        """
        if not isinstance(response, ChatCompletion):
            return ""

        if not response.choices:
            return ""

        message = response.choices[0].message
        return message.content or ""

    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls.
        """
        if not isinstance(response, ChatCompletion):
            return False

        if not response.choices:
            return False

        message = response.choices[0].message
        return bool(message.tool_calls)

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from Kimi ChatCompletion response.

        Args:
            response: ChatCompletion object from Kimi API

        Returns:
            List of tool call dictionaries with name, arguments, and id.
        """
        if not isinstance(response, ChatCompletion):
            return []

        if not response.choices:
            return []

        message = response.choices[0].message
        if not message.tool_calls:
            return []

        # Debug: Print raw tool calls from API
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
            raw_tool_calls = []
            for tc in message.tool_calls:
                raw_tool_calls.append({
                    'id': tc.id,
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    }
                })
            KimiDebugger.print_tool_call_received(raw_tool_calls)

        tool_calls: List[Dict[str, Any]] = []

        for tool_call in message.tool_calls:
            try:
                # ChatCompletion tool_calls have: id, type, function
                # function has: name, arguments (as string)
                arguments = tool_call.function.arguments

                # Parse arguments string to dict if needed
                if isinstance(arguments, str):
                    try:
                        # Handle empty string or whitespace-only string
                        if not arguments or not arguments.strip():
                            parsed_args = {}
                        else:
                            parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        # If parsing fails, return empty dict (not the string!)
                        print(f"[WARNING] Failed to parse arguments as JSON: {arguments}")
                        parsed_args = {}
                else:
                    parsed_args = arguments if arguments else {}

                tool_calls.append({
                    "name": tool_call.function.name,
                    "arguments": parsed_args,
                    "id": tool_call.id
                })
            except Exception as exc:
                print(f"[WARNING] Failed to parse tool call: {exc}")
                continue

        # Debug: Print extracted tool calls
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
            KimiDebugger.print_extracted_tool_calls(tool_calls)

        return tool_calls

    @staticmethod
    def format_response_for_storage(
        response,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AssistantMessage:
        """
        Format Kimi ChatCompletion response for storage in message history.

        This method creates standardized message objects optimized for:
        - Database storage efficiency
        - Frontend rendering consistency
        - Cross-LLM compatibility (following Gemini/Anthropic pattern)

        Args:
            response: ChatCompletion object from Kimi API
            tool_calls: Pre-extracted tool calls (optional). If provided, reuses these
                       instead of re-extracting to ensure consistent IDs.

        Returns:
            AssistantMessage formatted for storage with tool_use blocks in content array.
        """
        if not isinstance(response, ChatCompletion):
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        content_blocks: List[Dict[str, Any]] = []

        # Extract text content
        text_content = KimiResponseProcessor.extract_text_content(response)
        if text_content:
            content_blocks.append({"type": "text", "text": text_content})

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = KimiResponseProcessor.extract_tool_calls(response)

        # Add tool_use blocks to content array (following Gemini/Anthropic pattern)
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

        return message

    @staticmethod
    def extract_web_search_sources(response, debug: bool = False) -> List[Dict[str, Any]]:
        """
        Extract web search sources from Kimi response.

        Kimi supports web search through the $web_search builtin_function tool.
        Search results are integrated directly into the response text.
        """
        sources = []

        if not isinstance(response, ChatCompletion):
            return sources

        if not response.choices:
            return sources

        # Check if web search tool was used
        message = response.choices[0].message
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if hasattr(tool_call, 'function') and tool_call.function.name == '$web_search':
                    # Web search was performed
                    # Kimi integrates results into text, so we mark it
                    sources.append({
                        "title": "Kimi Web Search",
                        "url": "",
                        "snippet": "Search results integrated into response",
                        "type": "web_search"
                    })

        if debug and sources:
            print(f"[DEBUG] Extracted {len(sources)} web search sources from Kimi response")

        return sources


__all__ = ['KimiResponseProcessor']
