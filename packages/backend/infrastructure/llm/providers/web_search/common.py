"""Shared helpers for provider-specific web search."""

from __future__ import annotations

from typing import Any, Dict, Optional, List

from backend.domain.models.messages import BaseMessage, UserMessage
from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
from backend.infrastructure.llm.shared.utils.provider_registry import get_message_formatter_class


_DEFAULT_MAX_USES: Dict[str, int] = {
    "google": 10,
    "anthropic": 10,
    "openai": 5,
    "moonshot": 1,
    "zhipu": 1,
}


def get_default_max_uses(provider_name: str) -> int:
    return _DEFAULT_MAX_USES.get(provider_name, 5)


def format_search_result(
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


def format_search_error(query: str, error_message: str) -> Dict[str, Any]:
    return format_search_result(query, "", [], error_message)


def _build_search_user_message(query: str) -> UserMessage:
    return UserMessage(role="user", content=query)


def build_search_context(llm_client, query: str) -> List[Dict[str, Any]]:
    messages: List[BaseMessage] = [_build_search_user_message(query)]
    formatter_class = get_message_formatter_class(llm_client.provider_name.lower())
    return formatter_class.format_messages(messages)


async def perform_search(
    llm_client,
    query: str,
    tool_schemas: List[Any],
    *,
    thinking_level: Optional[str] = None,
) -> Dict[str, Any]:
    context_contents = build_search_context(llm_client, query)
    api_config = llm_client.build_api_config(DEFAULT_WEB_SEARCH_SYSTEM_PROMPT, tool_schemas)

    response = await llm_client.call_api_with_context(
        context_contents=context_contents,
        api_config=api_config,
        thinking_level=thinking_level,
    )

    response_text = llm_client.extract_text(response)
    sources = llm_client.extract_web_search_sources(response)

    if not response_text:
        return format_search_error(query, "No search results found")

    return format_search_result(query, response_text, sources)
