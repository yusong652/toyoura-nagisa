"""
Web Search Service - Application layer web search orchestration.
"""

import json
from typing import Dict, Any, Optional, List
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT


async def perform_web_search(
    llm_client,
    query: str,
    max_uses: Optional[int] = None,
) -> Dict[str, Any]:
    provider_name = _get_provider_name(llm_client)

    if max_uses is None:
        if provider_name == "google":
            max_uses = 10
        elif provider_name == "anthropic":
            max_uses = 10
        elif provider_name == "openai":
            max_uses = 5
        elif provider_name in ("moonshot", "zhipu"):
            max_uses = 1
        else:
            max_uses = 5

    max_uses_value: int = max_uses if max_uses is not None else 5

    if provider_name == "google":
        return await _perform_google_search(llm_client, query)
    if provider_name == "anthropic":
        return await _perform_anthropic_search(llm_client, query, max_uses_value)
    if provider_name == "openai":
        return await _perform_openai_search(llm_client, query)
    if provider_name == "moonshot":
        return await _perform_moonshot_search(llm_client, query)
    if provider_name == "zhipu":
        return await _perform_zhipu_search(llm_client, query)

    return {
        "error": f"Unsupported LLM type: {provider_name}",
        "query": query,
    }

def _format_search_result(
    query: str,
    response_text: str,
    sources: List[Dict[str, Any]],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    if response_text:
        parts = [response_text]
        if sources:
            parts.append("\n\n---\n**Sources:**")
            for i, source in enumerate(sources, 1):
                title = source.get("title", "Unknown")
                url = source.get("url", "")
                if url:
                    parts.append(f"{i}. [{title}]({url})")
                else:
                    parts.append(f"{i}. {title}")
        response_text = "\n".join(parts)

    return {
        "query": query,
        "response_text": response_text,
        "sources": sources,
        "total_sources": len(sources),
        "error": error,
    }


def _format_search_error(query: str, error_message: str) -> Dict[str, Any]:
    return _format_search_result(query, "", [], error_message)


def _build_search_user_message(query: str) -> UserMessage:
    return UserMessage(role="user", content=query)


def _get_provider_name(llm_client) -> str:
    provider_name = getattr(llm_client, "provider_name", None)
    if not provider_name:
        raise ValueError("LLM client is missing provider_name")
    return provider_name.lower()


async def _perform_google_search(llm_client, query: str) -> Dict[str, Any]:
    from google.genai import types

    tool_schemas = [types.Tool(google_search=types.GoogleSearch())]
    return await _perform_search(llm_client, query, tool_schemas)


async def _perform_anthropic_search(llm_client, query: str, max_uses: int) -> Dict[str, Any]:
    tool_schemas = [{
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": max_uses,
    }]
    return await _perform_search(llm_client, query, tool_schemas)


async def _perform_openai_search(llm_client, query: str) -> Dict[str, Any]:
    tool_schemas = [{"type": "web_search"}]
    return await _perform_search(llm_client, query, tool_schemas)


async def _perform_moonshot_search(llm_client, query: str) -> Dict[str, Any]:
    tool_schemas = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
    context_contents = _build_search_context(llm_client, query)
    api_config = llm_client.build_api_config(DEFAULT_WEB_SEARCH_SYSTEM_PROMPT, tool_schemas)

    finish_reason = None
    choice = None
    response: Any = None

    while finish_reason is None or finish_reason == "tool_calls":
        response = await llm_client.call_api_with_context(
            context_contents=context_contents,
            api_config=api_config,
        )

        if not response.choices:
            return _format_search_error(query, "No search results found")

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "tool_calls" and choice.message.tool_calls:
            # Add assistant message with tool calls to context
            context_contents.append(choice.message.model_dump())

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

                # Add tool result message to context
                context_contents.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_call_name,
                    "content": tool_result_content,
                })

    if response is None:
        return _format_search_error(query, "No valid response")
    if not choice:
        return _format_search_error(query, "No valid response")

    response_text = llm_client.extract_text(response)
    sources = llm_client.extract_web_search_sources(response)

    return _format_search_result(query, response_text, sources)


async def _perform_zhipu_search(llm_client, query: str) -> Dict[str, Any]:
    tool_schemas = [
        {
            "type": "web_search",
            "web_search": {
                "search_query": query,
                "search_result": True,
            },
        }
    ]
    return await _perform_search(
        llm_client,
        query,
        tool_schemas,
        thinking_level="default",  # No thinking for web search
    )


def _build_search_context(llm_client, query: str) -> List[Dict[str, Any]]:
    messages: List[BaseMessage] = [_build_search_user_message(query)]
    return llm_client.format_messages(messages)


async def _perform_search(
    llm_client,
    query: str,
    tool_schemas: List[Any],
    *,
    thinking_level: Optional[str] = None,
) -> Dict[str, Any]:
    context_contents = _build_search_context(llm_client, query)
    api_config = llm_client.build_api_config(DEFAULT_WEB_SEARCH_SYSTEM_PROMPT, tool_schemas)

    response = await llm_client.call_api_with_context(
        context_contents=context_contents,
        api_config=api_config,
        thinking_level=thinking_level,
    )

    response_text = llm_client.extract_text(response)
    sources = llm_client.extract_web_search_sources(response)

    if not response_text:
        return _format_search_error(query, "No search results found")

    return _format_search_result(query, response_text, sources)
