"""
Kimi-specific web search generator.

Performs web searches using Kimi's built-in $web_search tool.
"""

from typing import Dict, Any, List, cast
import json

from openai.types.chat import ChatCompletion

from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT


class KimiWebSearchGenerator(BaseWebSearchGenerator):
    """
    Kimi-specific web search using the built-in $web_search tool.

    Kimi provides a native web search capability through the $web_search
    builtin_function tool, which is called via the Chat Completions API.
    """

    async def perform_web_search(
        self,
        query: str,
        debug: bool = False,
        **kwargs  # Accept additional parameters for compatibility (e.g., max_uses)
    ) -> Dict[str, Any]:
        """
        Perform a web search using Kimi's built-in $web_search tool.

        Args:
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters (accepted for compatibility)

        Returns:
            Dictionary containing search results with sources and metadata
        """
        if debug:
            print(f"[KimiWebSearch] Starting web search with query: {query}")
            if kwargs:
                print(f"[KimiWebSearch] Additional params (accepted): {kwargs}")

        try:
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)

            # Get Kimi configuration for model
            llm_settings = get_llm_settings()
            kimi_config = llm_settings.get_kimi_config()
            model = kimi_config.model

            if debug:
                print(f"[KimiWebSearch] Using model: {model}")

            # Prepare messages for web search
            messages = [
                {
                    "role": "system",
                    "content": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            # Declare Kimi's builtin $web_search tool
            # Format according to official documentation
            tools = [
                {
                    "type": "builtin_function",  # Kimi-specific: use builtin_function
                    "function": {
                        "name": "$web_search",  # Built-in web search function
                    },
                }
            ]

            if debug:
                print(f"[KimiWebSearch] Messages: {messages}")
                print(f"[KimiWebSearch] Tools: {tools}")

            # Call Kimi API with web search tool - handle tool_calls loop
            # Kimi's web search requires a two-step process:
            # 1. First call returns tool_calls with search request
            # 2. Return tool results, second call generates final response
            finish_reason = None
            choice = None
            search_content_total_tokens = 0
            iteration = 0

            while finish_reason is None or finish_reason == "tool_calls":
                iteration += 1
                if debug:
                    print(f"[KimiWebSearch] API call iteration {iteration}")
                # Direct async API call (no thread wrapper needed)
                response: ChatCompletion = await self.client.chat.completions.create(
                    model=model,
                    messages=cast(Any, messages),
                    tools=cast(Any, tools),
                    temperature=kimi_config.temperature,
                )

                if debug:
                    print(f"[KimiWebSearch] API response received")
                    print(f"[KimiWebSearch] Response choices: {len(response.choices)}")

                if not response.choices:
                    if debug:
                        print("[KimiWebSearch] No response choices found")
                    return BaseWebSearchGenerator.format_search_error(query, "No search results found")

                choice = response.choices[0]
                finish_reason = choice.finish_reason

                if debug:
                    print(f"[KimiWebSearch] Finish reason: {finish_reason}")
                    current_content = choice.message.content or ""
                    print(f"[KimiWebSearch] Current message content length: {len(current_content)}")
                    if current_content:
                        print(f"[KimiWebSearch] Content preview: {current_content[:200]}...")

                # Handle tool calls
                if finish_reason == "tool_calls" and choice.message.tool_calls:
                    # Add assistant message with tool calls to history
                    messages.append(choice.message.model_dump())

                    if debug:
                        print(f"[KimiWebSearch] Processing {len(choice.message.tool_calls)} tool calls")

                    # Process each tool call
                    for tool_call in choice.message.tool_calls:
                        # Access function attributes safely for type checking
                        function = getattr(tool_call, 'function', None)
                        if not function:
                            continue

                        tool_call_name = getattr(function, 'name', '')
                        tool_call_arguments_str = getattr(function, 'arguments', '{}')
                        tool_call_arguments = json.loads(tool_call_arguments_str)

                        if debug:
                            print(f"[KimiWebSearch] Tool call: {tool_call_name}")

                        if tool_call_name == "$web_search":
                            # Extract search content token usage
                            usage_info = tool_call_arguments.get("usage", {})
                            search_content_total_tokens = usage_info.get("total_tokens", 0)

                            if debug:
                                print(f"[KimiWebSearch] Search content tokens: {search_content_total_tokens}")
                                print(f"[KimiWebSearch] Tool call arguments keys: {list(tool_call_arguments.keys())}")

                            # For Kimi, we just return the arguments as-is
                            tool_result = tool_call_arguments
                        else:
                            tool_result = {"error": f"Unknown tool: {tool_call_name}"}

                        # Add tool result to messages
                        tool_call_id = getattr(tool_call, 'id', '')
                        tool_result_content = json.dumps(tool_result, ensure_ascii=False)

                        if debug:
                            print(f"[KimiWebSearch] Tool result content length: {len(tool_result_content)}")
                            print(f"[KimiWebSearch] Tool result preview: {tool_result_content[:300]}...")

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_call_name,
                            "content": tool_result_content,
                        })

                        if debug:
                            print(f"[KimiWebSearch] Total messages in history: {len(messages)}")

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)

            if not choice:
                return BaseWebSearchGenerator.format_search_error(query, "No valid response")

            # Verify we got a complete response
            if finish_reason != "stop":
                if debug:
                    print(f"[KimiWebSearch] WARNING: Expected finish_reason='stop', got '{finish_reason}'")

            # Extract final response content
            response_text = choice.message.content or ""

            if debug:
                print(f"[KimiWebSearch] Loop completed after {iteration} iterations")
                print(f"[KimiWebSearch] Final finish_reason: {finish_reason}")
                print(f"[KimiWebSearch] Final response text length: {len(response_text)}")
                print(f"[KimiWebSearch] Final response text: {response_text}")
                print(f"[KimiWebSearch] Search tokens used: {search_content_total_tokens}")

            # Kimi integrates search results directly into the response
            sources: List[Dict[str, Any]] = []
            # Always add a source if we got a valid response after tool calls
            if response_text and iteration > 1:  # iteration > 1 means tool was called
                source_info = {
                    "title": "Kimi Web Search",
                    "url": "",
                    "snippet": "Search results integrated into response"
                }
                if search_content_total_tokens > 0:
                    source_info["snippet"] = f"Search results integrated (tokens: {search_content_total_tokens})"
                sources.append(source_info)

            if debug:
                print(f"[KimiWebSearch] Extracted {len(sources)} sources")

            # Format result using base class method
            result = BaseWebSearchGenerator.format_search_result(
                query=query,
                response_text=response_text,
                sources=sources
            )

            BaseWebSearchGenerator.debug_search_results(
                len(sources), len(response_text), debug
            )

            return result

        except Exception as e:
            error_msg = f"Kimi web search failed: {str(e)}"
            if debug:
                print(f"[KimiWebSearch] ERROR: {error_msg}")
                import traceback
                print(f"[KimiWebSearch] Traceback: {traceback.format_exc()}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)
