"""Moonshot web search provider."""

from __future__ import annotations

import json
from typing import Any, Dict

from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
from ..web_search.common import build_search_context, format_search_error, format_search_result


async def perform_moonshot_search(
    llm_client,
    query: str,
    *,
    max_uses: int,
) -> Dict[str, Any]:
    tool_schemas = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
    context_contents = build_search_context(llm_client, query)
    api_config = llm_client.build_api_config(DEFAULT_WEB_SEARCH_SYSTEM_PROMPT, tool_schemas)

    finish_reason = None
    choice = None
    response: Any = None

    while finish_reason is None or finish_reason == "tool_calls":
        response = await llm_client.call_api_with_context(
            context_contents=context_contents,
            api_config=api_config,
            thinking_level="low",  # Explicitly disable thinking for web search
        )

        if not response.choices:
            return format_search_error(query, "No search results found")

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "tool_calls" and choice.message.tool_calls:
            from backend.infrastructure.llm.providers.moonshot.response_processor import (
                MoonshotResponseProcessor,
            )

            assistant_message = MoonshotResponseProcessor.format_response_for_context(response)
            if not assistant_message:
                assistant_message = choice.message.model_dump()

            tool_calls = assistant_message.get("tool_calls") or []
            if tool_calls and "reasoning_content" not in assistant_message:
                assistant_message["reasoning_content"] = ""

            for tool_call in tool_calls:
                if tool_call.get("type") == "builtin_function":
                    tool_call["type"] = "function"

            context_contents.append(assistant_message)

            for tool_call in choice.message.tool_calls:
                function = getattr(tool_call, "function", None)
                if not function:
                    continue

                tool_call_name = getattr(function, "name", "")
                tool_call_arguments_str = getattr(function, "arguments", "{}")
                tool_call_arguments = json.loads(tool_call_arguments_str)

                if tool_call_name == "$web_search":
                    tool_result = tool_call_arguments
                else:
                    tool_result = {"error": f"Unknown tool: {tool_call_name}"}

                tool_call_id = getattr(tool_call, "id", "")
                tool_result_content = json.dumps(tool_result, ensure_ascii=False)

                context_contents.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_call_name,
                        "content": tool_result_content,
                    }
                )

    if response is None or not choice:
        return format_search_error(query, "No valid response")

    response_text = llm_client.extract_text(response)
    sources = llm_client.extract_web_search_sources(response)

    return format_search_result(query, response_text, sources)
