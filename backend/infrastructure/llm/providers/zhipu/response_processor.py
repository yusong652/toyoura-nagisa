"""
Zhipu (智谱) Response Processor

Handles processing of Zhipu API responses from zai SDK.

Zhipu uses ChatCompletion-like format similar to OpenAI Chat Completions API.
"""

import json
from typing import List, Dict, Any, Optional
from backend.domain.models.messages import AssistantMessage
from backend.infrastructure.llm.base.response_processor import BaseResponseProcessor
from .debug import ZhipuDebugger


class ZhipuResponseProcessor(BaseResponseProcessor):
    """
    Process Zhipu API responses using ChatCompletion-like format from zai SDK.

    Supports reasoning_content extraction for GLM thinking models.
    """

    @staticmethod
    def extract_text_content(response) -> str:
        """
        Extract text content from Zhipu response.

        Args:
            response: Response object from zai SDK

        Returns:
            Extracted text content as a single string.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return ""

        message = response.choices[0].message
        return getattr(message, 'content', '') or ""

    @staticmethod
    def extract_reasoning_content(response) -> Optional[str]:
        """
        Extract reasoning content from Zhipu GLM Thinking response.

        GLM models with thinking enabled expose a `reasoning_content` field that contains
        the model's intermediate reasoning/thinking process before the final answer.

        Args:
            response: Response object from zai SDK

        Returns:
            Extracted reasoning content as a string, or None if not available.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return None

        message = response.choices[0].message

        # Access reasoning_content attribute if it exists (GLM Thinking models)
        reasoning_content = getattr(message, 'reasoning_content', None)

        return reasoning_content if reasoning_content else None

    @staticmethod
    def has_tool_calls(response) -> bool:
        """
        Check if response contains tool calls.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return False

        message = response.choices[0].message
        return bool(hasattr(message, 'tool_calls') and message.tool_calls)

    @staticmethod
    def extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        Extract tool calls from Zhipu response.

        Args:
            response: Response object from zai SDK

        Returns:
            List of tool call dictionaries with name, arguments, and id.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return []

        message = response.choices[0].message
        if not hasattr(message, 'tool_calls') or not message.tool_calls:
            return []

        # Debug: Print raw tool calls from API
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
            raw_tool_calls = []
            for tc in message.tool_calls:
                function = getattr(tc, 'function', None)
                if function:
                    # Handle both object and dict formats in debug output too
                    if isinstance(function, dict):
                        func_name = function.get('name', '')
                        func_args = function.get('arguments', '')
                    else:
                        func_name = getattr(function, 'name', '')
                        func_args = getattr(function, 'arguments', '')

                    raw_tool_calls.append({
                        'id': tc.id,
                        'function': {
                            'name': func_name,
                            'arguments': func_args
                        }
                    })
            print(f"[DEBUG] Zhipu raw tool calls: {raw_tool_calls}")

        tool_calls: List[Dict[str, Any]] = []

        for tool_call in message.tool_calls:
            try:
                # Tool calls have: id, type, function
                # function has: name, arguments (as string)
                function = getattr(tool_call, 'function', None)
                if not function:
                    continue

                # Handle both object and dict formats
                # zai SDK might return either depending on the response structure
                if isinstance(function, dict):
                    function_name = function.get('name', '')
                    arguments = function.get('arguments', '')
                else:
                    # Object with attributes
                    function_name = getattr(function, 'name', '')
                    arguments = getattr(function, 'arguments', '')

                # Parse arguments string to dict if needed
                if isinstance(arguments, str):
                    try:
                        # Handle empty string or whitespace-only string
                        if not arguments or not arguments.strip():
                            parsed_args = {}
                        else:
                            parsed_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        # If parsing fails, return empty dict
                        print(f"[WARNING] Failed to parse Zhipu tool arguments as JSON: {arguments}")
                        parsed_args = {}
                else:
                    parsed_args = arguments if arguments else {}

                tool_calls.append({
                    "name": function_name,
                    "arguments": parsed_args,
                    "id": tool_call.id
                })
            except Exception as exc:
                print(f"[WARNING] Failed to parse Zhipu tool call: {exc}")
                continue

        # Debug: Print extracted tool calls
        from backend.config.llm import get_llm_settings
        if get_llm_settings().debug:
            print(f"[DEBUG] Zhipu extracted tool calls: {tool_calls}")

        return tool_calls

    @staticmethod
    def format_response_for_storage(
        response,
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> AssistantMessage:
        """
        Format Zhipu response for storage in message history.

        Args:
            response: Response object from zai SDK
            tool_calls: Pre-extracted tool calls (optional)

        Returns:
            AssistantMessage formatted for storage with tool_use blocks in content array.
        """
        if not hasattr(response, 'choices') or not response.choices:
            return AssistantMessage(role="assistant", content=[{"type": "text", "text": ""}])

        content_blocks: List[Dict[str, Any]] = []

        # Extract reasoning content first (GLM Thinking models)
        reasoning_content = ZhipuResponseProcessor.extract_reasoning_content(response)
        # Filter pure whitespace: use strip() to check, but keep original formatting
        if reasoning_content and reasoning_content.strip():
            content_blocks.append({"type": "thinking", "thinking": reasoning_content.strip()})

        # Extract text content
        text_content = ZhipuResponseProcessor.extract_text_content(response)
        # Filter pure whitespace: use strip() to check, but keep original formatting
        if text_content and text_content.strip():
            content_blocks.append({"type": "text", "text": text_content.strip()})

        # Reuse pre-extracted tool calls if provided, otherwise extract now
        if tool_calls is None:
            tool_calls = ZhipuResponseProcessor.extract_tool_calls(response)

        # Add tool_use blocks to content array
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
        Extract web search sources from Zhipu response.

        Zhipu supports web search through the web_search tool type.
        """
        sources = []

        if not hasattr(response, 'choices') or not response.choices:
            return sources

        # Check if web search tool was used
        message = response.choices[0].message
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                if getattr(tool_call, 'type', '') == 'web_search':
                    # Web search was performed
                    sources.append({
                        "title": "Zhipu Web Search",
                        "url": "",
                        "snippet": "Search results integrated into response",
                        "type": "web_search"
                    })

        if debug and sources:
            print(f"[DEBUG] Extracted {len(sources)} web search sources from Zhipu response")

        return sources


__all__ = ['ZhipuResponseProcessor']
